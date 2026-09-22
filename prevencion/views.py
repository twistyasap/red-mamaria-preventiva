import json
import random
import requests
import os

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.conf import settings


from .models import (
    PreguntaEducativa,
    OpcionRespuesta,
    RespuestaUsuario,
    AnalisisEcografia,
)


# ============================================================
# REGISTRO DE USUARIO
# ============================================================

def registro_usuario(request):

    if request.method == 'POST':

        usuario = request.POST.get('username')
        correo = request.POST.get('email')
        clave = request.POST.get('password')

        if User.objects.filter(username=usuario).exists():

            messages.error(
                request,
                'El nombre de usuario ya existe. Intenta con otro.'
            )

            return redirect('registro')

        nuevo_usuario = User.objects.create_user(
            username=usuario,
            email=correo,
            password=clave
        )

        nuevo_usuario.save()

        login(request, nuevo_usuario)

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

        usuario = request.POST.get('username')
        clave = request.POST.get('password')

        user = authenticate(
            request,
            username=usuario,
            password=clave
        )

        if user is not None:

            login(request, user)

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

    return render(
        request,
        'prevencion/inicio.html'
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

    # Guardar respuesta del usuario
    if request.method == 'POST':

        pregunta_id = request.POST.get('pregunta_id')
        opcion_id = request.POST.get('opcion_id')

        if pregunta_id and opcion_id:

            pregunta = get_object_or_404(
                PreguntaEducativa,
                id=pregunta_id
            )

            opcion = get_object_or_404(
                OpcionRespuesta,
                id=opcion_id
            )

            RespuestaUsuario.objects.update_or_create(
                usuario=request.user,
                pregunta=pregunta,
                defaults={
                    'opcion_seleccionada': opcion,
                    'es_correcta': opcion.es_correcta
                }
            )

            return redirect(
                'educativo_sesion',
                tipo_sesion=tipo_sesion
            )

    preguntas = PreguntaEducativa.objects.filter(
        sesion=tipo_sesion
    ).prefetch_related(
        'opciones'
    )

    respuestas_usuario = RespuestaUsuario.objects.filter(
        usuario=request.user,
        pregunta__sesion=tipo_sesion
    ).select_related(
        'opcion_seleccionada'
    )

    respuestas_dict = {
        respuesta.pregunta_id:
        respuesta.opcion_seleccionada_id
        for respuesta in respuestas_usuario
    }

    for pregunta in preguntas:

        pregunta.opcion_respondida_id = respuestas_dict.get(
            pregunta.id
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

    historial = AnalisisEcografia.objects.filter(
        usuario=request.user
    ).order_by(
        '-fecha_analisis'
    )[:5]

    context = {
        'resultado': resultado,
        'historial': historial,
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

    # Primero intenta obtenerla desde settings.py.
    # Como respaldo, intenta directamente desde Windows / entorno.
    api_key_settings = getattr(
        settings,
        'GEMINI_API_KEY',
        None
    )

    api_key_entorno = os.getenv(
        'GEMINI_API_KEY'
    )

    api_key = (
        api_key_settings
        or api_key_entorno
    )


    # ========================================================
    # DEBUG TEMPORAL
    # ========================================================

    print("")
    print("========== DEBUG SONIA ==========")

    print(
        "settings.GEMINI_API_KEY:",
        bool(api_key_settings)
    )

    print(
        "Largo settings:",
        len(api_key_settings or "")
    )

    print(
        "os.getenv GEMINI_API_KEY:",
        bool(api_key_entorno)
    )

    print(
        "Largo getenv:",
        len(api_key_entorno or "")
    )

    print(
        "API final disponible:",
        bool(api_key)
    )

    print(
        "Largo API final:",
        len(api_key or "")
    )

    print("=================================")
    print("")


    # ========================================================
    # 3. VALIDAR API KEY
    # ========================================================

    if not api_key:

        print(
            "SONIA ERROR: No se encontró GEMINI_API_KEY."
        )

        return JsonResponse(
            {
                'respuesta':
                'La inteligencia artificial no está disponible '
                'en este momento.'
            },
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

        "generationConfig": {
            "maxOutputTokens": 700
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
    # 7. MODELOS
    # ========================================================

    modelos = [
        "gemini-3.8-flash",
        "gemini-3.7-flash",
    ]


    response = None
    res_data = None
    modelo_utilizado = None


    # ========================================================
    # 8. INTENTAR CONSULTAR GEMINI
    # ========================================================

    for modelo in modelos:

        url = (
            "https://generativelanguage.googleapis.com/"
            f"v1beta/models/{modelo}:generateContent"
        )

        print(
            f"SONIA: intentando responder con {modelo}"
        )

        try:

            response = requests.post(
                url,
                json=payload,
                headers=headers,
                timeout=30
            )

        except requests.exceptions.Timeout:

            print(
                f"SONIA: timeout con {modelo}"
            )

            continue

        except requests.exceptions.RequestException as error:

            print(
                f"SONIA: error de conexión con {modelo}:",
                error
            )

            continue


        # ====================================================
        # Convertir la respuesta a JSON
        # ====================================================

        try:

            res_data = response.json()

        except ValueError:

            print(
                f"SONIA: {modelo} devolvió respuesta no JSON."
            )

            print(
                response.text
            )

            continue


        # ====================================================
        # RESPUESTA CORRECTA
        # ====================================================

        if response.status_code == 200:

            modelo_utilizado = modelo

            print(
                f"SONIA: respuesta correcta con {modelo}"
            )

            break


        # ====================================================
        # ERROR DE GEMINI
        # ====================================================

        mensaje_error = (
            res_data
            .get('error', {})
            .get('message', '')
        )

        mensaje_error_minuscula = (
            mensaje_error.lower()
        )


        print(
            f"SONIA: error con {modelo}"
        )

        print(
            "Código:",
            response.status_code
        )

        print(
            "Mensaje:",
            mensaje_error
        )


        # ====================================================
        # ERRORES TEMPORALES
        # ====================================================

        error_temporal = (

            response.status_code in [
                429,
                500,
                502,
                503,
                504
            ]

            or

            "high demand"
            in mensaje_error_minuscula

            or

            "overloaded"
            in mensaje_error_minuscula

            or

            "temporarily unavailable"
            in mensaje_error_minuscula

            or

            "try again later"
            in mensaje_error_minuscula
        )


        if error_temporal:

            print(
                f"SONIA: {modelo} no está disponible temporalmente."
            )

            continue


        # Si es otro error, detenemos los intentos
        break


    # ========================================================
    # 9. NINGÚN MODELO RESPONDIÓ
    # ========================================================

    if (
        response is None
        or response.status_code != 200
        or res_data is None
    ):

        print(
            "SONIA: ninguno de los modelos pudo responder."
        )

        if res_data:

            print(
                "Última respuesta Gemini:",
                res_data
            )

        return JsonResponse(
            {
                'respuesta':
                'Estoy teniendo dificultades para responder '
                'en este momento. Intenta nuevamente '
                'en unos segundos.'
            },
            status=503
        )


    # ========================================================
    # 10. EXTRAER RESPUESTA
    # ========================================================

    try:

        candidates = res_data.get(
            'candidates',
            []
        )

        if not candidates:

            print(
                "SONIA: Gemini no devolvió candidatos."
            )

            print(
                res_data
            )

            return JsonResponse(
                {
                    'respuesta':
                    'No pude generar una respuesta en este momento.'
                }
            )


        content = candidates[0].get(
            'content',
            {}
        )


        parts = content.get(
            'parts',
            []
        )


        if not parts:

            print(
                "SONIA: Gemini no devolvió partes de texto."
            )

            print(
                res_data
            )

            return JsonResponse(
                {
                    'respuesta':
                    'No pude generar una respuesta en este momento.'
                }
            )


        # Puede existir más de una parte.
        textos = []

        for part in parts:

            texto = part.get(
                'text'
            )

            if texto:

                textos.append(
                    texto
                )


        texto_respuesta = (
            '\n'.join(textos).strip()
        )


        if not texto_respuesta:

            return JsonResponse(
                {
                    'respuesta':
                    'No pude generar una respuesta en este momento.'
                }
            )


        print(
            f"SONIA: respuesta enviada con {modelo_utilizado}"
        )


        return JsonResponse(
            {
                'respuesta': texto_respuesta
            }
        )


    # ========================================================
    # 11. ERROR INESPERADO
    # ========================================================

    except Exception as error:

        print(
            "SONIA: error procesando la respuesta:",
            error
        )

        print(
            "Respuesta completa:",
            res_data
        )

        return JsonResponse(
            {
                'respuesta':
                'Ocurrió un error al procesar la respuesta. '
                'Intenta nuevamente.'
            },
            status=500
        )