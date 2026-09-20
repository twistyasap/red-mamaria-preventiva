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

from .models import PreguntaEducativa, AnalisisEcografia


def registro_usuario(request):
    if request.method == 'POST':
        usuario = request.POST.get('username')
        correo = request.POST.get('email')
        clave = request.POST.get('password')

        if User.objects.filter(username=usuario).exists():
            messages.error(request, 'El nombre de usuario ya existe. Intenta con otro.')
            return redirect('registro')

        nuevo_usuario = User.objects.create_user(username=usuario, email=correo, password=clave)
        nuevo_usuario.save()

        login(request, nuevo_usuario)
        return redirect('inicio')

    return render(request, 'prevencion/registro.html')


def iniciar_sesion(request):
    if request.method == 'POST':
        usuario = request.POST.get('username')
        clave = request.POST.get('password')

        user = authenticate(request, username=usuario, password=clave)
        if user is not None:
            login(request, user)
            return redirect('inicio')
        else:
            messages.error(request, 'Usuario o contraseña incorrectos.')
            return redirect('iniciar_sesion')

    return render(request, 'prevencion/iniciar_sesion.html')


def cerrar_sesion(request):
    logout(request)
    return redirect('iniciar_sesion')


@login_required(login_url='iniciar_sesion')
def inicio(request):
    return render(request, 'prevencion/inicio.html')


@login_required(login_url='iniciar_sesion')
def educativo_menu(request):
    return render(request, 'prevencion/menu_educativo.html')


@login_required(login_url='iniciar_sesion')
def educativo_sesion(request, tipo_sesion):
    nombres_sesion = {
        'S1': 'Sesión 1: Mitos vs Realidades',
        'S2': 'Sesión 2: Preguntas Clave',
        'S3': 'Sesión 3: Verdadero o Falso',
    }
    
    # Se añade prefetch_related('opciones') para traer las alternativas A, B, C y D de la Sesión 2
    preguntas = PreguntaEducativa.objects.filter(sesion=tipo_sesion).prefetch_related('opciones')
    nombre = nombres_sesion.get(tipo_sesion, 'Sesión Educativa')
    
    context = {
        'preguntas': preguntas,
        'nombre_sesion': nombre,
        'codigo_sesion': tipo_sesion
    }
    return render(request, 'prevencion/sesion_educativa.html', context)


@login_required(login_url='iniciar_sesion')
def analisis_imagen(request):
    resultado = None

    if request.method == 'POST':
        imagen = request.FILES.get('imagen_original')

        if not imagen:
            messages.error(request, 'Debes seleccionar una imagen antes de continuar.')
            return redirect('analisis_imagen')

        porcentaje_riesgo = round(random.uniform(5, 40), 1)
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
        messages.success(request, 'Imagen analizada correctamente.')

    historial = AnalisisEcografia.objects.filter(usuario=request.user).order_by('-fecha_analisis')[:5]

    context = {
        'resultado': resultado,
        'historial': historial,
    }
    return render(request, 'prevencion/analisis_imagen.html', context)


@login_required(login_url='iniciar_sesion')
def asistente_virtual(request):
    return render(request, 'prevencion/asistente_virtual.html')


@login_required(login_url='iniciar_sesion')
@require_POST
def asistente_virtual_mensaje(request):
    """
    Endpoint AJAX para la asistente virtual Sonia.
    """
    try:
        data = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        data = {}

    mensaje_usuario = (data.get('mensaje') or '').strip()

    if not mensaje_usuario:
        return JsonResponse({'error': 'Mensaje vacío.'}, status=400)

    try:
        api_key = getattr(settings, 'GEMINI_API_KEY', None)
        if not api_key:
            return JsonResponse({'respuesta': 'Falta configurar GEMINI_API_KEY en settings.py.'})

        # URL con el modelo actualizado gemini-1.5-flash
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"

        prompt_sistema = (
            "Eres Sonia, una asistente virtual empática, cercana y profesional especializada en prevención de salud mamaria en Chile. "
            "Tu objetivo es resolver dudas comunes sobre autoexamen, mamografías y síntomas de alerta. "
            "Responde siempre de forma clara, directa y amable. "
            "IMPORTANTE: No das diagnósticos médicos definitivos. Siempre recomienda consultar a un profesional de la salud o acudir a un CESFAM/centro médico ante dudas o anomalías."
        )

        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": f"Instrucción: {prompt_sistema}\n\nPregunta: {mensaje_usuario}"}
                    ]
                }
            ]
        }

        headers = {
            "Content-Type": "application/json"
        }

        response = requests.post(url, json=payload, headers=headers, timeout=10)
        res_data = response.json()

        if response.status_code == 200:
            texto_respuesta = res_data['candidates'][0]['content']['parts'][0]['text']
            return JsonResponse({'respuesta': texto_respuesta})
        else:
            detalles = res_data.get('error', {}).get('message', response.text)
            return JsonResponse({'respuesta': f'Ocurrió un error al procesar tu solicitud: {detalles}'})

    except Exception as e:
        print(f"Error en Sonia Chatbot: {e}")
        return JsonResponse({'respuesta': f'Ocurrió un error al procesar tu solicitud: {str(e)}'})