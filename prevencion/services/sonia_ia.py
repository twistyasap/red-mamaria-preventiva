"""
Conexión de Sonia con los modelos de inteligencia artificial.

La respuesta se genera en streaming: el texto se envía al navegador a
medida que el modelo lo escribe, en vez de esperar la respuesta completa.

Proveedores, en orden:
  1. Groq (si existe GROQ_API_KEY): gratis y muy rápido.
  2. Gemini de Google (si existe GEMINI_API_KEY), de respaldo.
Si un modelo falla ANTES de escribir la primera palabra, se pasa al
siguiente sin esperas. Si ninguno responde, se usa una respuesta de
respaldo escrita a mano (respuestas_respaldo.py).
"""

import json
import time

import requests

from django.conf import settings

from .respuestas_respaldo import obtener_respuesta_respaldo


PROMPT_SISTEMA = """
Eres Sonia, una asistente virtual educativa especializada
en prevención, educación y orientación general sobre salud
mamaria y cáncer de mama.

Tu función es ayudar a los usuarios de una plataforma
educativa sobre prevención del cáncer de mama.

Debes responder siempre en español.

CARACTERÍSTICAS DE TUS RESPUESTAS:

- Sé clara.
- Sé amable.
- Sé cercana.
- Sé profesional.
- Utiliza lenguaje fácil de comprender.
- Entrega respuestas relativamente breves.
- Evita respuestas excesivamente largas.
- Puedes utilizar listas cuando sea útil.
- Evita alarmar innecesariamente al usuario.
- No inventes información médica.
- Evita tecnicismos innecesarios.
- Si utilizas un término médico, explícalo de forma sencilla.
- Responde en 150 palabras o menos, salvo que el usuario pida
  más detalle.
- Usa solo párrafos cortos, listas con guiones y **negritas**.
  No uses tablas, títulos con # ni líneas separadoras (---).

PUEDES RESPONDER SOBRE:

- cáncer de mama
- prevención
- factores de riesgo
- mamografías
- ecografías mamarias
- autoobservación mamaria
- cambios o señales de alerta en las mamas
- controles preventivos
- hábitos saludables
- detección temprana
- educación en salud mamaria
- antecedentes familiares
- preparación para una mamografía
- frecuencia de controles preventivos

REGLAS MÉDICAS:

1. No realices diagnósticos médicos definitivos.

2. No afirmes que una persona tiene o no tiene cáncer.

3. No reemplaces la evaluación de un médico, matrona
   u otro profesional de salud.

4. Si una persona describe un síntoma o anomalía,
   entrega información educativa y recomienda consultar
   con un profesional de salud.

5. Si existen señales potencialmente preocupantes,
   recomienda solicitar atención médica.

6. Si corresponden al contexto chileno, puedes mencionar
   CESFAM, consultorios, centros médicos u hospitales.

7. No indiques medicamentos ni tratamientos personalizados
   sin evaluación profesional.

8. No entregues porcentajes personales de probabilidad
   de tener cáncer basándote solamente en síntomas.

9. Si una pregunta requiere evaluación clínica,
   explica que debe ser revisada por un profesional.

Si el usuario realiza una pregunta completamente ajena
a salud mamaria o cáncer de mama, explica amablemente
que tu función principal es orientar sobre salud mamaria.

No comiences todas las respuestas diciendo "Hola".
Responde directamente a la pregunta del usuario.

Ten en cuenta los mensajes anteriores de la conversación: si el
usuario hace una pregunta de seguimiento (por ejemplo "¿y en
hombres?"), respóndela en relación a lo que se venía hablando.
"""

MAX_MENSAJES_HISTORIAL = 10
MAX_LARGO_MENSAJE_HISTORIAL = 2000

# Largo máximo de la respuesta (las respuestas de Sonia son breves).
MAX_TOKENS_RESPUESTA = 1500

# (conexión, lectura): la lectura es el máximo de silencio permitido
# entre trozos de texto. Si un modelo no empieza a escribir en ese
# tiempo, se pasa al siguiente.
TIEMPO_CONEXION = 4
TIEMPO_LECTURA = 15

# Tope total para probar modelos antes de usar la respuesta de respaldo.
TIEMPO_MAXIMO_TOTAL = 30


class ErrorIA(Exception):
    """Un modelo no pudo responder.

    clave_invalida=True indica que la API key del proveedor no sirve,
    así que no vale la pena probar sus otros modelos.
    """

    def __init__(self, mensaje, clave_invalida=False):
        super().__init__(mensaje)
        self.clave_invalida = clave_invalida


# ============================================================
# HISTORIAL
# ============================================================

def armar_conversacion(historial, mensaje_usuario):
    """
    Convierte el historial que envía el navegador en una lista
    [{'rol': 'user'|'assistant', 'texto': ...}] que alterna roles,
    empieza con el usuario y termina con el mensaje nuevo.
    """

    roles = {
        'usuario': 'user',
        'sonia': 'assistant',
    }

    conversacion = []

    if isinstance(historial, list):

        for item in historial[-MAX_MENSAJES_HISTORIAL:]:

            if not isinstance(item, dict):
                continue

            rol = roles.get(item.get('rol'))
            texto = item.get('texto')

            if not rol or not isinstance(texto, str) or not texto.strip():
                continue

            texto = texto.strip()[:MAX_LARGO_MENSAJE_HISTORIAL]

            if conversacion and conversacion[-1]['rol'] == rol:
                conversacion[-1]['texto'] += '\n\n' + texto
            else:
                conversacion.append({'rol': rol, 'texto': texto})

    while conversacion and conversacion[0]['rol'] != 'user':
        conversacion.pop(0)

    if conversacion and conversacion[-1]['rol'] == 'user':
        conversacion.pop()

    conversacion.append({'rol': 'user', 'texto': mensaje_usuario})

    return conversacion


# ============================================================
# LECTURA DE STREAMS (Server-Sent Events)
# ============================================================

def _abrir_stream(nombre, url, headers, payload, timeout):

    # "identity" evita que la respuesta venga comprimida, porque la
    # compresión puede retener trozos de texto hasta juntar varios.
    headers = {**headers, 'Accept-Encoding': 'identity'}

    try:
        response = requests.post(
            url,
            json=payload,
            headers=headers,
            timeout=timeout,
            stream=True
        )

    except requests.exceptions.RequestException as error:
        raise ErrorIA(f"{nombre}: error de conexión ({error})")

    if response.status_code == 200:
        return response

    try:
        datos = response.json()
        error = datos.get('error', {})
        mensaje_error = (
            error.get('message', '') if isinstance(error, dict) else str(error)
        )

    except ValueError:
        mensaje_error = response.text[:200]

    finally:
        response.close()

    raise ErrorIA(
        f"{nombre}: HTTP {response.status_code} - {mensaje_error}",
        clave_invalida=response.status_code in [401, 403] or (
            'api key' in mensaje_error.lower()
        )
    )


def _eventos_sse(nombre, response):
    """Entrega cada evento 'data: {...}' del stream como diccionario."""

    try:
        for linea in response.iter_lines():

            if not linea.startswith(b'data:'):
                continue

            contenido = linea[5:].strip()

            if contenido == b'[DONE]':
                return

            try:
                yield json.loads(contenido)
            except ValueError:
                continue

    except requests.exceptions.RequestException as error:
        raise ErrorIA(f"{nombre}: se cortó la conexión ({error})")

    finally:
        response.close()


# ============================================================
# GROQ (API compatible con OpenAI)
# ============================================================

def _stream_groq(modelo, conversacion, restante):

    nombre = f"groq/{modelo}"

    payload = {
        'model': modelo,
        'messages': [{'role': 'system', 'content': PROMPT_SISTEMA}] + [
            {'role': item['rol'], 'content': item['texto']}
            for item in conversacion
        ],
        'stream': True,
        'max_completion_tokens': MAX_TOKENS_RESPUESTA,
    }

    # Los modelos gpt-oss "razonan" antes de responder: con esfuerzo
    # bajo responden casi de inmediato.
    if 'gpt-oss' in modelo:
        payload['reasoning_effort'] = 'low'
        payload['include_reasoning'] = False

    response = _abrir_stream(
        nombre,
        'https://api.groq.com/openai/v1/chat/completions',
        {'Authorization': f"Bearer {settings.GROQ_API_KEY}"},
        payload,
        (TIEMPO_CONEXION, min(TIEMPO_LECTURA, restante))
    )

    for evento in _eventos_sse(nombre, response):

        if evento.get('error'):
            raise ErrorIA(f"{nombre}: {evento['error']}")

        for opcion in evento.get('choices') or []:
            texto = (opcion.get('delta') or {}).get('content')
            if texto:
                yield texto


# ============================================================
# GEMINI (Google)
# ============================================================

def _config_razonamiento_gemini(modelo):
    """
    Los Gemini Flash "piensan" antes de responder por defecto, lo que
    agrega varios segundos. Para un chat educativo no hace falta.
    """

    if modelo.startswith('gemini-3'):
        nivel = 'minimal' if 'flash' in modelo else 'low'
        return {'thinkingLevel': nivel}

    if modelo.startswith('gemini-2.5-flash'):
        return {'thinkingBudget': 0}

    return None


def _stream_gemini(modelo, conversacion, restante):

    nombre = f"gemini/{modelo}"

    config = {'maxOutputTokens': MAX_TOKENS_RESPUESTA}
    razonamiento = _config_razonamiento_gemini(modelo)

    if razonamiento:
        config['thinkingConfig'] = razonamiento

    payload = {
        'system_instruction': {'parts': [{'text': PROMPT_SISTEMA}]},
        'contents': [
            {
                'role': 'model' if item['rol'] == 'assistant' else 'user',
                'parts': [{'text': item['texto']}],
            }
            for item in conversacion
        ],
        'generationConfig': config,
    }

    response = _abrir_stream(
        nombre,
        'https://generativelanguage.googleapis.com/v1beta/'
        f'models/{modelo}:streamGenerateContent?alt=sse',
        {'x-goog-api-key': settings.GEMINI_API_KEY},
        payload,
        (TIEMPO_CONEXION, min(TIEMPO_LECTURA, restante))
    )

    for evento in _eventos_sse(nombre, response):

        if evento.get('error'):
            raise ErrorIA(f"{nombre}: {evento['error']}")

        for candidato in evento.get('candidates') or []:
            for parte in (candidato.get('content') or {}).get('parts', []):
                if parte.get('text') and not parte.get('thought'):
                    yield parte['text']


# ============================================================
# ORQUESTACIÓN
# ============================================================

def modelos_disponibles():
    """Lista [(proveedor, modelo, funcion)] en el orden en que se prueban."""

    modelos = []

    if settings.GROQ_API_KEY:
        modelos += [
            ('groq', modelo, _stream_groq)
            for modelo in settings.GROQ_MODELS
        ]

    if settings.GEMINI_API_KEY:
        modelos += [
            ('gemini', modelo, _stream_gemini)
            for modelo in settings.GEMINI_MODELS
        ]

    return modelos


def generar_respuesta(historial, mensaje_usuario):
    """
    Generador de eventos para el navegador:
      ('texto', 'trozo de texto')  -> varias veces
      ('fin', {'respaldo': bool})  -> una vez, al final
    """

    conversacion = armar_conversacion(historial, mensaje_usuario)
    inicio = time.monotonic()
    errores = []
    proveedores_sin_clave = set()

    for proveedor, modelo, funcion in modelos_disponibles():

        if proveedor in proveedores_sin_clave:
            continue

        restante = TIEMPO_MAXIMO_TOTAL - (time.monotonic() - inicio)

        if restante < 3:
            errores.append(f"Se alcanzó el tope de {TIEMPO_MAXIMO_TOTAL} s")
            break

        escribio = False

        try:
            for texto in funcion(modelo, conversacion, restante):
                escribio = True
                yield 'texto', texto

        except ErrorIA as error:

            errores.append(str(error))
            print(f"SONIA: {error}")

            if error.clave_invalida:
                proveedores_sin_clave.add(proveedor)

            if not escribio:
                continue

            # Se cortó a la mitad: se deja lo que alcanzó a escribir.
            yield 'fin', {'respaldo': False, 'incompleta': True}
            return

        if escribio:
            print(f"SONIA: respuesta de {proveedor}/{modelo} en "
                  f"{time.monotonic() - inicio:.1f} s")
            yield 'fin', {'respaldo': False}
            return

        errores.append(f"{proveedor}/{modelo}: respuesta vacía")
        print(f"SONIA: {errores[-1]}")

    print("SONIA: ningún modelo respondió, se usa respuesta de respaldo")

    respuesta = obtener_respuesta_respaldo(mensaje_usuario)

    if settings.SONIA_MOSTRAR_ERRORES:
        respuesta += '\n\n[DEBUG] ' + (
            '\n'.join(errores) or 'No hay modelos configurados.'
        )

    yield 'texto', respuesta
    yield 'fin', {'respaldo': True}
