"""
Lista los modelos de Groq disponibles para tu GROQ_API_KEY.

Uso:
    python manage.py modelos_groq
"""

import requests

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):

    help = 'Lista los modelos de Groq que puede usar tu GROQ_API_KEY.'

    def handle(self, *args, **options):

        api_key = settings.GROQ_API_KEY

        if not api_key:
            raise CommandError(
                'No se encontró GROQ_API_KEY. Agrégala al archivo .env'
            )

        response = requests.get(
            'https://api.groq.com/openai/v1/models',
            headers={'Authorization': f'Bearer {api_key}'},
            timeout=30
        )

        datos = response.json()

        if response.status_code != 200:
            error = datos.get('error', {})
            raise CommandError(
                f"HTTP {response.status_code}: "
                f"{error.get('message', datos) if isinstance(error, dict) else error}"
            )

        modelos = sorted(
            modelo['id']
            for modelo in datos.get('data', [])
            if modelo.get('active', True)
        )

        self.stdout.write('Modelos disponibles:\n')

        for modelo in modelos:
            marca = '  <- configurado' if modelo in settings.GROQ_MODELS else ''
            self.stdout.write(f'  {modelo}{marca}')

        faltantes = [
            modelo for modelo in settings.GROQ_MODELS
            if modelo not in modelos
        ]

        if faltantes:
            self.stdout.write(self.style.WARNING(
                '\nEstos modelos configurados NO existen para tu key: '
                + ', '.join(faltantes)
            ))
