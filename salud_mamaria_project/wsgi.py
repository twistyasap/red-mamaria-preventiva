"""
WSGI config for salud_mamaria_project project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.1/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'salud_mamaria_project.settings')

application = get_wsgi_application()


# En Vercel no hay una terminal para correr "python manage.py migrate",
# así que las migraciones pendientes se aplican al arrancar la app.
# Si no hay nada pendiente, Django solo lo revisa y sigue.
if os.environ.get('VERCEL') and os.environ.get('DATABASE_URL'):

    from django.core.management import call_command

    try:
        call_command('migrate', interactive=False, verbosity=1)
    except Exception as error:
        print('Error aplicando migraciones al arrancar:', error)
