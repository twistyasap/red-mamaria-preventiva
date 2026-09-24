"""
Lista los modelos de Gemini disponibles para tu GEMINI_API_KEY.

Uso:
    python manage.py modelos_gemini
"""

import requests

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):

    help = 'Lista los modelos de Gemini que puede usar tu GEMINI_API_KEY.'

    def handle(self, *args, **options):

        api_key = (settings.GEMINI_API_KEY or '').strip()

        if not api_key:
            raise CommandError(
                'No se encontró GEMINI_API_KEY. Agrégala al archivo .env'
            )

        response = requests.get(
            'https://generativelanguage.googleapis.com/v1beta/models',
            headers={'x-goog-api-key': api_key},
            params={'pageSize': 1000},
            timeout=30
        )

        datos = response.json()

        if response.status_code != 200:
            raise CommandError(
                f"HTTP {response.status_code}: "
                f"{datos.get('error', {}).get('message', datos)}"
            )

        modelos = [
            modelo['name'].removeprefix('models/')
            for modelo in datos.get('models', [])
            if 'generateContent' in modelo.get(
                'supportedGenerationMethods', []
            )
        ]

        self.stdout.write('Modelos que sirven para el chat:\n')

        for modelo in modelos:
            marca = '  <- configurado' if modelo in settings.GEMINI_MODELS else ''
            self.stdout.write(f'  {modelo}{marca}')

        faltantes = [
            modelo for modelo in settings.GEMINI_MODELS
            if modelo not in modelos
        ]

        if faltantes:
            self.stdout.write(self.style.WARNING(
                '\nEstos modelos configurados NO existen para tu key: '
                + ', '.join(faltantes)
            ))
