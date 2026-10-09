"""
Correos automáticos de la plataforma.

El envío nunca debe interrumpir lo que estaba haciendo la persona: si
Gmail falla o no responde, se registra el error y la página sigue normal.
"""

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string


ASUNTO_BIENVENIDA = (
    '🎀 Te damos la bienvenida a nuestra plataforma de prevención '
    'del cáncer de mama'
)


def enviar_bienvenida(usuario, enlace):
    """
    Envía el correo de bienvenida a un usuario recién registrado.

    Args:
        usuario: el User recién creado (se usa su nombre de usuario).
        enlace: dirección de la página, para el botón "Comenzar ahora".

    Returns:
        True si se envió, False si no (sin lanzar errores).
    """

    if not usuario.email:
        return False

    contexto = {
        'nombre': usuario.username,
        'enlace': enlace,
    }

    try:
        correo = EmailMultiAlternatives(
            subject=ASUNTO_BIENVENIDA,
            body=render_to_string('prevencion/correos/bienvenida.txt', contexto),
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[usuario.email],
        )
        correo.attach_alternative(
            render_to_string('prevencion/correos/bienvenida.html', contexto),
            'text/html'
        )
        correo.send()
        return True

    except Exception as error:
        print('CORREO: no se pudo enviar la bienvenida:', repr(error))
        return False
