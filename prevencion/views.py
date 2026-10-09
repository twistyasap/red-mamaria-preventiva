import json
import time
import requests

from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email


from .services.respuestas_respaldo import obtener_respuesta_respaldo
from .services.correos import enviar_bienvenida
from .services.analisis_cnn import (
    analizar_mamografia,
    ImagenNoValida,
    UMBRAL_AMARILLO,
    UMBRAL_ROJO,
)
from .models import PreguntaEducativa


# ============================================================
# REGISTRO DE USUARIO
# ============================================================

def registro_usuario(request):

    if request.method == 'POST':

        usuario = (request.POST.get('username') or '').strip()
        correo = (request.POST.get('email') or '').strip()
        clave = request.POST.get('password') or ''

        # Datos para volver a llenar el formulario si hay un error
        contexto = {
            'datos': {
                'username': usuario,
                'email': correo,
            }
        }

        campos_obligatorios = [
            (usuario, 'Nombre de usuario'),
            (correo, 'Correo Electrónico'),
            (clave, 'Contraseña'),
        ]

        faltantes = [
            nombre for valor, nombre in campos_obligatorios
            if not valor
        ]

        if faltantes:

            for nombre in faltantes:
                messages.error(
                    request,
                    f'Falta llenar el campo {nombre}.'
                )

            return render(
                request,
                'prevencion/registro.html',
                contexto
            )

        # El correo debe ser válido: ahí llega la bienvenida
        try:
            validate_email(correo)
        except ValidationError:
            messages.error(
                request,
                'El correo no tiene un formato válido (ej: nombre@correo.com).'
            )
            return render(
                request,
                'prevencion/registro.html',
                contexto
            )

        if User.objects.filter(username=usuario).exists():

            messages.error(
                request,
                'El nombre de usuario ya existe. Intenta con otro.'
            )

            return render(
                request,
                'prevencion/registro.html',
                contexto
            )

        nuevo_usuario = User.objects.create_user(
            username=usuario,
            email=correo,
            password=clave
        )

        nuevo_usuario.save()

        login(request, nuevo_usuario)

        # El Inicio mostrará el pop-up de bienvenida una vez
        request.session['bienvenida'] = 'registro'

        # Correo de bienvenida. Si falla, la cuenta queda creada igual.
        enviar_bienvenida(
            nuevo_usuario,
            request.build_absolute_uri('/')
        )

        return redirect('inicio')

    return render(
        request,
        'prevencion/registro.html'
    )


# ============================================================
# INICIO DE SESIÓN
# ============================================================

def iniciar_sesion(request):

    if request.method == 'POST':

        usuario = (request.POST.get('username') or '').strip()
        clave = request.POST.get('password') or ''

        faltantes = [
            nombre for valor, nombre in [
                (usuario, 'Usuario'),
                (clave, 'Contraseña'),
            ]
            if not valor
        ]

        if faltantes:

            for nombre in faltantes:
                messages.error(
                    request,
                    f'Falta llenar el campo {nombre}.'
                )

            return render(
                request,
                'prevencion/iniciar_sesion.html',
                {'usuario_ingresado': usuario}
            )

        user = authenticate(
            request,
            username=usuario,
            password=clave
        )

        if user is not None:

            login(request, user)

            # El Inicio mostrará el pop-up de bienvenida una vez
            request.session['bienvenida'] = 'login'

            return redirect('inicio')

        else:

            messages.error(
                request,
                'Usuario o contraseña incorrectos.'
            )

            return redirect('iniciar_sesion')

    return render(
        request,
        'prevencion/iniciar_sesion.html'
    )


# ============================================================
# CERRAR SESIÓN
# ============================================================

def cerrar_sesion(request):

    logout(request)

    return redirect('iniciar_sesion')


# ============================================================
# PÁGINA DE INICIO
# ============================================================

@login_required(login_url='iniciar_sesion')
def inicio(request):

    # 'registro', 'login' o None. Se saca de la sesión para que el
    # pop-up aparezca solo la primera vez que se llega al Inicio.
    bienvenida = request.session.pop('bienvenida', None)

    return render(
        request,
        'prevencion/inicio.html',
        {
            'bienvenida': bienvenida,
        }
    )


# ============================================================
# MENÚ EDUCATIVO
# ============================================================

@login_required(login_url='iniciar_sesion')
def educativo_menu(request):

    return render(
        request,
        'prevencion/menu_educativo.html'
    )


# ============================================================
# SESIONES EDUCATIVAS
# ============================================================

@login_required(login_url='iniciar_sesion')
def educativo_sesion(request, tipo_sesion):

    nombres_sesion = {
        'S1': 'Sesión 1: Mitos vs Realidades',
        'S2': 'Sesión 2: Preguntas Clave',
        'S3': 'Sesión 3: Verdadero o Falso',
    }

    # Las respuestas se corrigen y se recuerdan en el navegador
    # (ver el script de sesion_educativa.html).
    preguntas = PreguntaEducativa.objects.filter(
        sesion=tipo_sesion
    ).prefetch_related(
        'opciones'
    )

    nombre = nombres_sesion.get(
        tipo_sesion,
        'Sesión Educativa'
    )

    context = {
        'preguntas': preguntas,
        'nombre_sesion': nombre,
        'codigo_sesion': tipo_sesion
    }

    return render(
        request,
        'prevencion/sesion_educativa.html',
        context
    )


# ============================================================
# ANÁLISIS DE IMAGEN
# ============================================================

@login_required(login_url='iniciar_sesion')
def analisis_imagen(request):
    """
    Analiza la mamografía con la CNN y muestra el resultado.
    La imagen se procesa en memoria y NO se guarda en ningún lado.
    """

    resultado = None
    error = None

    if request.method == 'POST':

        imagen = request.FILES.get('imagen_original')

        if not imagen:

            error = 'Debes seleccionar una imagen antes de continuar.'

        else:

            try:
                resultado = analizar_mamografia(imagen.read())

            except ImagenNoValida as e:
                error = str(e)

            except Exception as e:
                print('ANÁLISIS: error inesperado:', repr(e))
                error = (
                    'Ocurrió un problema al analizar la imagen. '
                    'Intenta nuevamente en unos minutos.'
                )

            finally:
                # Se descarta el archivo subido (no se guarda)
                imagen.close()

    return render(
        request,
        'prevencion/analisis_imagen.html',
        {
            'resultado': resultado,
            'error': error,
            # Rangos del semáforo (vienen del config.json del modelo)
            'rango_verde': round(UMBRAL_AMARILLO * 100),
            'rango_rojo': round(UMBRAL_ROJO * 100),
        }
    )


# ============================================================
# PÁGINA DEL ASISTENTE VIRTUAL
# ============================================================

@login_required(login_url='iniciar_sesion')
def asistente_virtual(request):

    return render(
        request,
        'prevencion/asistente_virtual.html'
    )


# ============================================================
# CHATBOT SONIA - GEMINI
# ============================================================

def respuesta_error_sonia(mensaje, detalle, status):
    """
    Respuesta de error del chat. En tu PC (SONIA_MOSTRAR_ERRORES) agrega
    el detalle técnico para poder ver en el chat qué falló realmente;
    en Vercel el público solo ve el mensaje amable.
    """

    if settings.SONIA_MOSTRAR_ERRORES:
        mensaje = f"{mensaje}\n\n[DEBUG] {detalle}"

    return JsonResponse(
        {
            'respuesta': mensaje,
            # El navegador no guarda estos mensajes en el historial
            'es_error': True,
        },
        status=status
    )


MAX_MENSAJES_HISTORIAL = 10
MAX_LARGO_MENSAJE_HISTORIAL = 2000


def armar_historial(historial):
    """
    Convierte los mensajes anteriores del chat (enviados por el navegador)
    al formato "contents" de Gemini, para que Sonia recuerde la conversación.

    Cada elemento viene como {"rol": "usuario" | "sonia", "texto": "..."}.
    Se ignora lo que no tenga ese formato, se conservan solo los últimos
    mensajes y se juntan los mensajes seguidos del mismo rol.
    """

    if not isinstance(historial, list):
        return []

    roles = {
        'usuario': 'user',
        'sonia': 'model',
    }

    contents = []

    for item in historial[-MAX_MENSAJES_HISTORIAL:]:

        if not isinstance(item, dict):
            continue

        rol = roles.get(item.get('rol'))
        texto = item.get('texto')

        if not rol or not isinstance(texto, str) or not texto.strip():
            continue

        texto = texto.strip()[:MAX_LARGO_MENSAJE_HISTORIAL]

        if contents and contents[-1]['role'] == rol:
            contents[-1]['parts'][0]['text'] += '\n\n' + texto
        else:
            contents.append({'role': rol, 'parts': [{'text': texto}]})

    # La conversación debe empezar con un mensaje del usuario
    while contents and contents[0]['role'] != 'user':
        contents.pop(0)

    # Y terminar en Sonia, porque a continuación va el mensaje nuevo
    if contents and contents[-1]['role'] == 'user':
        contents.pop()

    return contents


def consultar_gemini(modelo, payload, headers, timeout=20):
    """
    Envía el mensaje a un modelo de Gemini.

    Retorna (datos, error, reintentable):
      - datos: el JSON de la respuesta si salió bien, o None.
      - error: texto del error si falló.
      - reintentable: True si el error es temporal (saturación, límite
        de uso, timeout), False si no, y None si la API key es inválida.
    """

    url = (
        "https://generativelanguage.googleapis.com/"
        f"v1beta/models/{modelo}:generateContent"
    )

    try:

        response = requests.post(
            url,
            json=payload,
            headers=headers,
            timeout=timeout
        )

    except requests.exceptions.RequestException as error:

        return None, f"{modelo}: error de conexión ({error})", True

    try:

        datos = response.json()

    except ValueError:

        return (
            None,
            f"{modelo}: respuesta no JSON (HTTP {response.status_code})",
            True
        )

    if response.status_code == 200:
        return datos, None, False

    mensaje_error = datos.get('error', {}).get('message', '')
    error = f"{modelo}: HTTP {response.status_code} - {mensaje_error}"

    if response.status_code in [401, 403] or (
        'api key' in mensaje_error.lower()
    ):
        return None, error, None

    return None, error, response.status_code in [429, 500, 502, 503, 504]


@login_required(login_url='iniciar_sesion')
@require_POST
def asistente_virtual_mensaje(request):
    """
    Endpoint AJAX para la asistente virtual Sonia.
    """

    # ========================================================
    # 1. LEER MENSAJE DEL USUARIO
    # ========================================================

    try:
        data = json.loads(request.body or '{}')

    except json.JSONDecodeError:
        return JsonResponse(
            {
                'error': 'Formato JSON inválido.'
            },
            status=400
        )

    mensaje_usuario = (
        data.get('mensaje') or ''
    ).strip()

    if not mensaje_usuario:
        return JsonResponse(
            {
                'error': 'Mensaje vacío.'
            },
            status=400
        )


    # ========================================================
    # 2. OBTENER API KEY
    # ========================================================

    # Se lee desde settings.py, que a su vez la toma del archivo .env
    # (en tu PC) o de las Environment Variables (en Vercel).
    api_key = (
        getattr(settings, 'GEMINI_API_KEY', None) or ''
    ).strip()


    # ========================================================
    # 3. VALIDAR API KEY
    # ========================================================

    if not api_key:

        print(
            "SONIA ERROR: No se encontró GEMINI_API_KEY. "
            "Agrégala al archivo .env o a las variables de Vercel."
        )

        return respuesta_error_sonia(
            'La inteligencia artificial no está disponible '
            'en este momento.',
            'Falta GEMINI_API_KEY en el archivo .env.',
            status=500
        )


    # ========================================================
    # 4. INSTRUCCIONES DE SONIA
    # ========================================================

    prompt_sistema = """
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

6. Si corresponde al contexto chileno, puedes mencionar
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


    # ========================================================
    # 5. CREAR PAYLOAD PARA GEMINI
    # ========================================================

    payload = {

        "system_instruction": {
            "parts": [
                {
                    "text": prompt_sistema
                }
            ]
        },

        # Mensajes anteriores del chat + el mensaje nuevo, para que Sonia
        # pueda seguir la conversación.
        "contents": armar_historial(data.get('historial')) + [
            {
                "role": "user",

                "parts": [
                    {
                        "text": mensaje_usuario
                    }
                ]
            }
        ],

        # Los modelos Gemini recientes "piensan" antes de responder y esos
        # tokens cuentan dentro de este límite. Con un valor bajo la
        # respuesta puede llegar vacía, por eso se deja holgado.
        "generationConfig": {
            "maxOutputTokens": 4096
        }
    }


    # ========================================================
    # 6. HEADERS
    # ========================================================

    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": api_key
    }


    # ========================================================
    # 7. INTENTAR CONSULTAR GEMINI (modelo por modelo)
    # ========================================================

    # Cuando Google está saturado (503) el modelo que responde va
    # cambiando de un momento a otro, así que si todos fallan por un
    # error temporal se espera un poco y se intenta una ronda más.
    RONDAS = 2
    ESPERA_ENTRE_RONDAS = 2  # segundos

    # Segundos que se espera a cada modelo, y tope para todo el proceso:
    # al cumplirse, se deja de intentar y se usa la respuesta de respaldo,
    # para que la persona nunca espere demasiado.
    TIEMPO_ESPERA = 30
    TIEMPO_MAXIMO_TOTAL = 60
    inicio = time.monotonic()

    res_data = None
    modelo_utilizado = None
    errores = []
    modelos_pendientes = list(settings.GEMINI_MODELS)
    reintentables = []
    tiempo_agotado = False

    for ronda in range(1, RONDAS + 1):

        if ronda > 1:
            print(f"SONIA: todos saturados, ronda {ronda} en "
                  f"{ESPERA_ENTRE_RONDAS} s")
            time.sleep(ESPERA_ENTRE_RONDAS)

        reintentables = []

        for modelo in modelos_pendientes:

            tiempo_restante = (
                TIEMPO_MAXIMO_TOTAL - (time.monotonic() - inicio)
            )

            if tiempo_restante < 3:
                errores.append(
                    f"Se alcanzó el tope de {TIEMPO_MAXIMO_TOTAL} s"
                )
                tiempo_agotado = True
                break

            datos, error, reintentable = consultar_gemini(
                modelo,
                payload,
                headers,
                timeout=min(TIEMPO_ESPERA, tiempo_restante)
            )

            if datos is not None:
                res_data = datos
                modelo_utilizado = modelo
                break

            errores.append(f"[ronda {ronda}] {error}")
            print(f"SONIA: {errores[-1]}")

            # API key inválida o sin permisos: ningún otro modelo va a
            # funcionar, así que no tiene sentido seguir intentando.
            if reintentable is None:
                reintentables = []
                break

            if reintentable:
                reintentables.append(modelo)

        # Solo se repiten los modelos que fallaron por algo temporal
        # (saturación, límite de uso, timeout), no los inexistentes.
        if res_data is not None or not reintentables or tiempo_agotado:
            break

        modelos_pendientes = reintentables


    # ========================================================
    # 8. NINGÚN MODELO RESPONDIÓ
    # ========================================================

    # En vez de mostrar un error, Sonia entrega información general
    # preescrita sobre el tema, para que el chat nunca quede sin respuesta.
    if res_data is None:

        print("SONIA: ningún modelo respondió, se usa respuesta de respaldo")

        respuesta = obtener_respuesta_respaldo(mensaje_usuario)

        if settings.SONIA_MOSTRAR_ERRORES:
            respuesta += '\n\n[DEBUG] ' + (
                '\n'.join(errores) or 'No hay modelos configurados.'
            )

        return JsonResponse(
            {
                'respuesta': respuesta,
                # El navegador la muestra, pero no la guarda en el
                # historial de la conversación.
                'respaldo': True,
            }
        )


    # ========================================================
    # 9. EXTRAER RESPUESTA
    # ========================================================

    candidates = res_data.get('candidates') or []

    if not candidates:

        # Suele pasar cuando Gemini bloquea el mensaje por seguridad.
        bloqueo = res_data.get('promptFeedback', {}).get('blockReason')

        return respuesta_error_sonia(
            'No pude generar una respuesta para ese mensaje. '
            'Intenta formularlo de otra manera.',
            f"{modelo_utilizado}: sin candidatos "
            f"(blockReason={bloqueo})",
            status=200
        )

    candidato = candidates[0]

    textos = [
        part.get('text', '')
        for part in candidato.get('content', {}).get('parts', [])
        # Las partes marcadas como "thought" son el razonamiento
        # interno del modelo, no la respuesta final.
        if not part.get('thought')
    ]

    texto_respuesta = '\n'.join(textos).strip()

    if not texto_respuesta:

        return respuesta_error_sonia(
            'No pude generar una respuesta en este momento. '
            'Intenta nuevamente.',
            f"{modelo_utilizado}: respuesta vacía "
            f"(finishReason={candidato.get('finishReason')})",
            status=200
        )

    print(f"SONIA: respuesta enviada con {modelo_utilizado}")

    return JsonResponse(
        {
            'respuesta': texto_respuesta
        }
    )
