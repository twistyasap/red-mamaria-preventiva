import json
import random
import requests

from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.conf import settings


from .models import (
    PreguntaEducativa,
    AnalisisEcografia,
)


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

    resultado = None

    if request.method == 'POST':

        imagen = request.FILES.get(
            'imagen_original'
        )

        if not imagen:

            messages.error(
                request,
                'Debes seleccionar una imagen antes de continuar.'
            )

            return redirect(
                'analisis_imagen'
            )

        # Resultado temporal mientras se integra la CNN real
        porcentaje_riesgo = round(
            random.uniform(5, 40),
            1
        )

        if porcentaje_riesgo < 15:

            rango_alerta = 'Verde'

        elif porcentaje_riesgo < 30:

            rango_alerta = 'Amarillo'

        else:

            rango_alerta = 'Rojo'

        analisis = AnalisisEcografia.objects.create(

            usuario=request.user,

            imagen_original=imagen,

            porcentaje_riesgo=porcentaje_riesgo,

            rango_alerta=rango_alerta,
        )

        resultado = analisis

        messages.success(
            request,
            'Imagen analizada correctamente.'
        )

    context = {
        'resultado': resultado,
    }

    return render(
        request,
        'prevencion/analisis_imagen.html',
        context
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
    Respuesta de error del chat. Con DEBUG activo agrega el detalle
    técnico para poder ver en el chat qué falló realmente.
    """

    if settings.DEBUG:
        mensaje = f"{mensaje}\n\n[DEBUG] {detalle}"

    return JsonResponse(
        {
            'respuesta': mensaje
        },
        status=status
    )


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

        "contents": [
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

    res_data = None
    modelo_utilizado = None
    errores = []

    for modelo in settings.GEMINI_MODELS:

        url = (
            "https://generativelanguage.googleapis.com/"
            f"v1beta/models/{modelo}:generateContent"
        )

        try:

            response = requests.post(
                url,
                json=payload,
                headers=headers,
                timeout=30
            )

        except requests.exceptions.RequestException as error:

            errores.append(f"{modelo}: error de conexión ({error})")
            print(f"SONIA: {errores[-1]}")
            continue

        try:

            datos = response.json()

        except ValueError:

            errores.append(
                f"{modelo}: respuesta no JSON "
                f"(HTTP {response.status_code})"
            )
            print(f"SONIA: {errores[-1]}")
            continue

        if response.status_code == 200:

            res_data = datos
            modelo_utilizado = modelo
            break

        mensaje_error = datos.get('error', {}).get('message', '')

        errores.append(
            f"{modelo}: HTTP {response.status_code} - {mensaje_error}"
        )
        print(f"SONIA: {errores[-1]}")

        # API key inválida o sin permisos: ningún otro modelo va a
        # funcionar, así que no tiene sentido seguir intentando.
        if response.status_code in [401, 403] or (
            'api key' in mensaje_error.lower()
        ):
            break

        # Cualquier otro error (modelo inexistente, saturado, límite de
        # uso, etc.) se intenta con el siguiente modelo.


    # ========================================================
    # 8. NINGÚN MODELO RESPONDIÓ
    # ========================================================

    if res_data is None:

        return respuesta_error_sonia(
            'Estoy teniendo dificultades para responder '
            'en este momento. Intenta nuevamente '
            'en unos segundos.',
            '\n'.join(errores) or 'No hay modelos configurados.',
            status=503
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
