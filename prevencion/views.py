import json
import time
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
import requests

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.password_validation import validate_password
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email

from .forms import FormularioUsuario, FormularioPerfil
from .models import Perfil, PreguntaEducativa, Recordatorio, RecordatorioListo
from .services.respuestas_respaldo import obtener_respuesta_respaldo
from .services.correos import enviar_bienvenida
from .services.analisis_cnn import (
    analizar_mamografias,
    ImagenNoValida,
    MAXIMO_IMAGENES,
    UMBRAL_AMARILLO,
    UMBRAL_ROJO,
    CONFIG as CONFIG_MODELO,
)


# ============================================================
# PÁGINA DE PRESENTACIÓN (LANDING)
# ============================================================

# Estudiantes que desarrollaron el proyecto (pie de página de la landing)
EQUIPO = [
    {
        'nombre': 'Diego Mesias', 'iniciales': 'DM',
        'linkedin': 'https://www.linkedin.com/in/diego-mesias/',
    },
    {
        'nombre': 'Matías Moya', 'iniciales': 'MM',
        'linkedin': 'https://www.linkedin.com/in/matiascristobal/',
        'portafolio': 'https://matiasmoya.vercel.app/',
    },
    {
        'nombre': 'Francisco Quiroz', 'iniciales': 'FQ',
        'linkedin': 'https://www.linkedin.com/in/francisco-javier-quiroz-corval%C3%A1n/',
    },
]


def landing(request):
    return render(
        request,
        'prevencion/landing.html',
        {'equipo': EQUIPO}
    )


# ============================================================
# TRANSPARENCIA: cómo funciona la IA y qué datos se guardan
# (pública; el tamaño de imagen sale del config.json del modelo)
# ============================================================

def transparencia(request):

    return render(
        request,
        'prevencion/transparencia.html',
        {
            'alto': CONFIG_MODELO['img_h'],
            'ancho': CONFIG_MODELO['img_w'],
        }
    )


# ============================================================
# PERFIL DE USUARIO (CORREGIDO)
# ============================================================

@login_required(login_url='iniciar_sesion')
def perfil_usuario(request):
    perfil, _ = Perfil.objects.get_or_create(usuario=request.user)

    if request.method == 'POST':
        form_usuario = FormularioUsuario(request.POST, instance=request.user)
        form_perfil = FormularioPerfil(request.POST, instance=perfil)

        if form_usuario.is_valid() and form_perfil.is_valid():
            form_usuario.save()
            form_perfil.save()
            messages.success(request, '¡Tu perfil ha sido actualizado con éxito!')
            return redirect('perfil_usuario')
    else:
        form_usuario = FormularioUsuario(instance=request.user)
        form_perfil = FormularioPerfil(instance=perfil)

    contexto = {
        'form_usuario': form_usuario,
        'form_perfil': form_perfil,
        'perfil': perfil
    }
    # AHORA BUSCA EN prevencion/perfil.html
    return render(request, 'prevencion/perfil.html', contexto)


# ============================================================
# REGISTRO DE USUARIO
# ============================================================

def registro_usuario(request):

    if request.method == 'POST':

        usuario = (request.POST.get('username') or '').strip()
        correo = (request.POST.get('email') or '').strip()
        clave = request.POST.get('password') or ''

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

        # Requisitos de la contraseña (mín. 8 caracteres, primera
        # mayúscula, un número, no demasiado común) definidos en
        # AUTH_PASSWORD_VALIDATORS de settings.py
        try:
            validate_password(
                clave,
                user=User(username=usuario, email=correo)
            )
        except ValidationError as error:
            for mensaje in error.messages:
                messages.error(request, mensaje)
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

        request.session['bienvenida'] = 'registro'

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

    # Si ya tiene la sesión abierta, no le pedimos las credenciales de nuevo
    if request.user.is_authenticated:
        return redirect('inicio')

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

    bienvenida = request.session.pop('bienvenida', None)
    pendientes, proximos = recordatorios_pendientes(request.user)

    return render(
        request,
        'prevencion/inicio.html',
        {
            'bienvenida': bienvenida,
            'pendientes': pendientes,
            'proximos': proximos,
        }
    )


# ============================================================
# MENÚ EDUCATIVO
# ============================================================

@login_required(login_url='iniciar_sesion')
def educativo_menu(request):

    preguntas_por_sesion = {
        sesion: list(
            PreguntaEducativa.objects.filter(sesion=sesion)
            .values_list('id', flat=True)
        )
        for sesion in ['S1', 'S2', 'S3']
    }

    return render(
        request,
        'prevencion/menu_educativo.html',
        {
            'preguntas_por_sesion': preguntas_por_sesion,
            'totales': {
                sesion: len(ids)
                for sesion, ids in preguntas_por_sesion.items()
            },
        }
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
        'codigo_sesion': tipo_sesion,
        'ids_preguntas': [pregunta.id for pregunta in preguntas],
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
    error = None

    if request.method == 'POST':

        # Una o varias imágenes (por ejemplo, una por cada vista del examen)
        imagenes = request.FILES.getlist('imagenes')

        if not imagenes:
            error = 'Debes seleccionar una imagen antes de continuar.'

        else:

            try:
                resultado = analizar_mamografias([imagen.read() for imagen in imagenes])

            except ImagenNoValida as e:
                error = str(e)

            except Exception as e:
                print('ANÁLISIS: error inesperado:', repr(e))
                error = (
                    'Ocurrió un problema al analizar las imágenes. '
                    'Intenta nuevamente en unos minutos.'
                )

            finally:
                for imagen in imagenes:
                    imagen.close()

    return render(
        request,
        'prevencion/analisis_imagen.html',
        {
            'resultado': resultado,
            'error': error,
            'rango_verde': round(UMBRAL_AMARILLO * 100),
            'rango_rojo': round(UMBRAL_ROJO * 100),
            'maximo_imagenes': MAXIMO_IMAGENES,        }
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

    if settings.SONIA_MOSTRAR_ERRORES:
        mensaje = f"{mensaje}\n\n[DEBUG] {detalle}"

    return JsonResponse(
        {
            'respuesta': mensaje,
            'es_error': True,
        },
        status=status
    )


MAX_MENSAJES_HISTORIAL = 10
MAX_LARGO_MENSAJE_HISTORIAL = 2000


def armar_historial(historial):

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

    while contents and contents[0]['role'] != 'user':
        contents.pop(0)

    if contents and contents[-1]['role'] == 'user':
        contents.pop()

    return contents


def consultar_gemini(modelo, payload, headers, timeout=20):

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

    api_key = (
        getattr(settings, 'GEMINI_API_KEY', None) or ''
    ).strip()

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

    payload = {
        "system_instruction": {
            "parts": [
                {
                    "text": prompt_sistema
                }
            ]
        },
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
        "generationConfig": {
            "maxOutputTokens": 4096
        }
    }

    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": api_key
    }

    RONDAS = 2
    ESPERA_ENTRE_RONDAS = 2
    TIEMPO_ESPERA = 30
    TIEMPO_MAXIMO_TOTAL = 60
    inicio_tiempo = time.monotonic()

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
                TIEMPO_MAXIMO_TOTAL - (time.monotonic() - inicio_tiempo)
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

            if reintentable is None:
                reintentables = []
                break

            if reintentable:
                reintentables.append(modelo)

        if res_data is not None or not reintentables or tiempo_agotado:
            break

        modelos_pendientes = reintentables

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
                'respaldo': True,
            }
        )

    candidates = res_data.get('candidates') or []

    if not candidates:

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

# ============================================================
# MIS RECORDATORIOS (calendario)
# ============================================================

# Opciones listas para elegir (el usuario también puede escribir otra)
RECORDATORIOS_SUGERIDOS = [
    'Hacer mi autoexamen de mamas',
    'Pedir hora para mi mamografía',
    'Control con mi médico o matrona',
    'Tomar mis medicamentos',
    'Hacer actividad física',
]
MAXIMO_RECORDATORIOS = 50


def _recordatorio_a_dict(recordatorio):
    return {
        'id': recordatorio.id,
        'titulo': recordatorio.titulo,
        'fecha': recordatorio.fecha.isoformat(),
        'hora': recordatorio.hora.strftime('%H:%M'),
        'repeticion': recordatorio.repeticion,
    }


@login_required(login_url='iniciar_sesion')
def recordatorios(request):
    return render(
        request,
        'prevencion/recordatorios.html',
        {
            'sugeridos': RECORDATORIOS_SUGERIDOS,
            'repeticiones': Recordatorio.REPETICIONES,
        }
    )


@login_required(login_url='iniciar_sesion')
def recordatorios_eventos(request):
    # El calendario pide los eventos del rango que está mostrando
    # (?start=2026-10-26T00:00:00-03:00&end=2026-12-07T00:00:00-03:00)
    try:
        desde = date.fromisoformat((request.GET.get('start') or '')[:10])
        hasta = date.fromisoformat((request.GET.get('end') or '')[:10])
    except ValueError:
        return JsonResponse({'error': 'Rango de fechas no válido.'}, status=400)

    # Como máximo unos 3 meses por consulta
    hasta = min(hasta, desde + timedelta(days=100))

    eventos = []
    for recordatorio in request.user.recordatorios.all():
        datos = _recordatorio_a_dict(recordatorio)
        for dia in recordatorio.ocurrencias(desde, hasta):
            eventos.append({
                'id': f'{recordatorio.id}-{dia.isoformat()}',
                'title': recordatorio.titulo,
                'start': f'{dia.isoformat()}T{datos["hora"]}',
                'extendedProps': datos,
            })

    return JsonResponse(eventos, safe=False)


@login_required(login_url='iniciar_sesion')
@require_POST
def recordatorio_guardar(request):
    try:
        datos = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({'error': 'Datos no válidos.'}, status=400)

    titulo = (datos.get('titulo') or '').strip()
    repeticion = datos.get('repeticion') or 'una'

    if not titulo:
        return JsonResponse({'error': 'Escribe qué quieres que te recordemos.'}, status=400)
    if len(titulo) > 120:
        return JsonResponse({'error': 'El recordatorio puede tener como máximo 120 caracteres.'}, status=400)
    if repeticion not in dict(Recordatorio.REPETICIONES):
        return JsonResponse({'error': 'Elige cada cuánto se repite.'}, status=400)
    try:
        fecha = date.fromisoformat(datos.get('fecha') or '')
        hora = datetime.strptime(datos.get('hora') or '', '%H:%M').time()
    except ValueError:
        return JsonResponse({'error': 'Elige un día y una hora válidos.'}, status=400)

    if datos.get('id'):
        recordatorio = get_object_or_404(Recordatorio, id=datos['id'], usuario=request.user)
    else:
        if request.user.recordatorios.count() >= MAXIMO_RECORDATORIOS:
            return JsonResponse(
                {'error': f'Puedes tener como máximo {MAXIMO_RECORDATORIOS} recordatorios. Borra alguno para crear otro.'},
                status=400
            )
        recordatorio = Recordatorio(usuario=request.user)

    recordatorio.titulo = titulo
    recordatorio.fecha = fecha
    recordatorio.hora = hora
    recordatorio.repeticion = repeticion
    recordatorio.save()

    return JsonResponse({'ok': True, 'recordatorio': _recordatorio_a_dict(recordatorio)})


@login_required(login_url='iniciar_sesion')
@require_POST
def recordatorio_borrar(request, id_recordatorio):
    recordatorio = get_object_or_404(Recordatorio, id=id_recordatorio, usuario=request.user)
    recordatorio.delete()
    return JsonResponse({'ok': True})


# ---------- Recordatorios pendientes (aviso en la página de inicio) ----------

# Los usuarios están en Chile; el servidor (Vercel) funciona en hora UTC
ZONA_CHILE = ZoneInfo('America/Santiago')
DIAS_PENDIENTES = 30   # se revisan solo los últimos 30 días
DIAS_PROXIMOS = 7      # y los próximos 7 días (se muestran en gris)
MAXIMO_PROXIMOS = 2
DIAS_SEMANA = ['lun', 'mar', 'mié', 'jue', 'vie', 'sáb', 'dom']
MESES = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic']


def _hora_am_pm(hora):
    return f'{hora.hour % 12 or 12}:{hora.minute:02d} {"AM" if hora.hour < 12 else "PM"}'


def _texto_dia(dia, hoy):
    if dia == hoy:
        return 'Hoy'
    if dia == hoy - timedelta(days=1):
        return 'Ayer'
    if dia == hoy + timedelta(days=1):
        return 'Mañana'
    return f'{DIAS_SEMANA[dia.weekday()]} {dia.day} {MESES[dia.month - 1]}'


def recordatorios_pendientes(usuario):
    """
    Recordatorios para la tarjeta del inicio:
    - pendientes: su fecha y hora ya llegaron y aún no se marcaron como listos
      (los más recientes primero)
    - próximos: los que vienen en los siguientes días (los más cercanos primero)
    """
    ahora = datetime.now(ZONA_CHILE).replace(tzinfo=None)
    hoy = ahora.date()

    pendientes, proximos = [], []
    for recordatorio in usuario.recordatorios.prefetch_related('listos'):
        # No se cuentan días anteriores a cuando se creó el recordatorio
        desde = max(hoy - timedelta(days=DIAS_PENDIENTES), recordatorio.creado.astimezone(ZONA_CHILE).date())
        listos = {listo.fecha for listo in recordatorio.listos.all()}

        for dia in recordatorio.ocurrencias(desde, hoy + timedelta(days=DIAS_PROXIMOS + 1)):
            if dia in listos:
                continue
            momento = datetime.combine(dia, recordatorio.hora)
            item = {
                'id': recordatorio.id,
                'titulo': recordatorio.titulo,
                'fecha': dia.isoformat(),
                'cuando': f'{_texto_dia(dia, hoy)}, {_hora_am_pm(recordatorio.hora)}',
                'momento': momento,
                # Milisegundos para que la página sepa cuándo pasarlo de gris a pendiente
                'momento_ms': int(momento.replace(tzinfo=ZONA_CHILE).timestamp() * 1000),
            }
            (pendientes if momento <= ahora else proximos).append(item)

    pendientes.sort(key=lambda p: p['momento'], reverse=True)
    proximos.sort(key=lambda p: p['momento'])
    return pendientes, proximos[:MAXIMO_PROXIMOS]


@login_required(login_url='iniciar_sesion')
@require_POST
def recordatorio_listo(request, id_recordatorio):
    recordatorio = get_object_or_404(Recordatorio, id=id_recordatorio, usuario=request.user)
    try:
        fecha = date.fromisoformat(json.loads(request.body).get('fecha') or '')
    except (ValueError, AttributeError, json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({'error': 'Fecha no válida.'}, status=400)

    # Solo se puede marcar un día en que de verdad toca el recordatorio
    if not recordatorio.ocurrencias(fecha, fecha + timedelta(days=1)):
        return JsonResponse({'error': 'Ese día no tiene este recordatorio.'}, status=400)

    RecordatorioListo.objects.get_or_create(recordatorio=recordatorio, fecha=fecha)
    return JsonResponse({'ok': True})
