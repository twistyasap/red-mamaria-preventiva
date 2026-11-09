"""
Requisitos propios para las contraseñas de Red Mamaria Preventiva.

Deben coincidir con la lista que se muestra en el formulario de
registro (static/prevencion/js/validacion_formularios.js).
"""
import re

from django.core.exceptions import ValidationError


class ValidadorClaveSegura:
    """La contraseña debe empezar con mayúscula y contener un número."""

    def validate(self, password, user=None):
        errores = []

        if not password or not password[0].isupper():
            errores.append(ValidationError(
                'La contraseña debe comenzar con una letra mayúscula.',
                code='clave_sin_mayuscula_inicial',
            ))

        if not re.search(r'\d', password or ''):
            errores.append(ValidationError(
                'La contraseña debe contener al menos un número.',
                code='clave_sin_numero',
            ))

        if errores:
            raise ValidationError(errores)

    def get_help_text(self):
        return 'Tu contraseña debe comenzar con mayúscula y contener al menos un número.'
