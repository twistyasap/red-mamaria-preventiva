"""
Carga las preguntas educativas (y sus opciones de la Sesión 2) desde
prevencion/fixtures/preguntas_iniciales.json.

Solo agrega las preguntas que no existan (se comparan por sesión y
enunciado), así que no duplica nada en bases que ya las tengan.
"""

import json
from pathlib import Path

from django.db import migrations


ARCHIVO = (
    Path(__file__).resolve().parent.parent
    / 'fixtures'
    / 'preguntas_iniciales.json'
)


def cargar_preguntas(apps, schema_editor):

    PreguntaEducativa = apps.get_model('prevencion', 'PreguntaEducativa')
    OpcionRespuesta = apps.get_model('prevencion', 'OpcionRespuesta')

    registros = json.loads(ARCHIVO.read_text(encoding='utf-8'))

    preguntas = [
        r for r in registros
        if r['model'] == 'prevencion.preguntaeducativa'
    ]

    opciones = [
        r for r in registros
        if r['model'] == 'prevencion.opcionrespuesta'
    ]

    for registro in preguntas:

        campos = registro['fields']

        pregunta, creada = PreguntaEducativa.objects.get_or_create(
            sesion=campos['sesion'],
            enunciado=campos['enunciado'],
            defaults={
                'respuesta_correcta': campos['respuesta_correcta'],
                'explicacion_medica': campos['explicacion_medica'],
            }
        )

        if not creada:
            continue

        # Opciones que pertenecían a esta pregunta en el archivo
        for opcion in opciones:

            if opcion['fields']['pregunta'] == registro['pk']:

                OpcionRespuesta.objects.create(
                    pregunta=pregunta,
                    texto_opcion=opcion['fields']['texto_opcion'],
                    es_correcta=opcion['fields']['es_correcta'],
                )


class Migration(migrations.Migration):

    dependencies = [
        ('prevencion', '0004_eliminar_respuestausuario'),
    ]

    operations = [
        migrations.RunPython(
            cargar_preguntas,
            migrations.RunPython.noop
        ),
    ]
