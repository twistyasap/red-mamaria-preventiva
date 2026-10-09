"""
Agrega preguntas a las 3 sesiones educativas (16 por sesión en total).

Solo agrega las que no existan (se comparan por sesión y enunciado), así
que no duplica nada si la migración se aplica en una base que ya las tiene.
"""

from django.db import migrations


# Sesión 1 (Mitos vs Realidades) y Sesión 3 (Verdadero o Falso):
# (enunciado, es_verdadero_o_realidad, explicación)
SESION_1 = [
    ("¿Usar desodorante o antitranspirante puede causar cáncer de mama?", False,
     "Mito: No existe evidencia científica que relacione el uso de desodorantes o antitranspirantes con el cáncer de mama."),
    ("¿Usar sostén con barras o muy ajustado causa cáncer de mama?", False,
     "Mito: El tipo de sostén no influye en el riesgo de cáncer de mama. Puedes usar el que te resulte más cómodo."),
    ("¿El riesgo de cáncer de mama aumenta con la edad?", True,
     "Realidad: La edad es uno de los principales factores de riesgo; la mayoría de los casos se diagnostica en mujeres mayores de 50 años."),
    ("¿Las mamas pequeñas tienen menos riesgo de desarrollar cáncer?", False,
     "Mito: El tamaño de las mamas no determina el riesgo. Todas las personas deben conocer sus mamas y asistir a sus controles."),
    ("¿El consumo de alcohol puede aumentar el riesgo de cáncer de mama?", True,
     "Realidad: El consumo de alcohol se asocia a un mayor riesgo; mientras más se consume, mayor es el riesgo."),
    ("¿La mamografía puede provocar o diseminar el cáncer de mama?", False,
     "Mito: La mamografía usa una dosis muy baja de radiación y la compresión no disemina el cáncer. Sus beneficios para la detección temprana son mucho mayores."),
    ("¿Tener implantes mamarios impide hacerse una mamografía?", False,
     "Mito: Las personas con implantes pueden y deben hacerse mamografías. Es importante avisar al personal de salud, que usará técnicas especiales."),
    ("¿La lactancia materna puede ayudar a reducir el riesgo de cáncer de mama?", True,
     "Realidad: Amamantar se asocia a una disminución del riesgo de cáncer de mama, especialmente cuando la lactancia es prolongada."),
    ("¿Las mujeres jóvenes no pueden tener cáncer de mama?", False,
     "Mito: Es menos frecuente en mujeres jóvenes, pero puede ocurrir. Ante cualquier cambio en las mamas, a cualquier edad, se debe consultar."),
]

SESION_3 = [
    ("El cáncer de mama es uno de los cánceres más frecuentes en las mujeres.", True,
     "Verdadero. Es uno de los cánceres más comunes en mujeres en el mundo, por eso la prevención y la detección temprana son tan importantes."),
    ("Si una mamografía sale normal, ya no es necesario volver a hacerse controles.", False,
     "Falso. Los controles deben repetirse con la frecuencia que indique el profesional de salud, aunque el último resultado haya sido normal."),
    ("El sobrepeso después de la menopausia puede aumentar el riesgo de cáncer de mama.", True,
     "Verdadero. Después de la menopausia, el exceso de grasa corporal se asocia a un mayor riesgo. Mantener un peso saludable ayuda a prevenir."),
    ("Los cambios en una mama solo deben revisarse si aparecen en ambas mamas.", False,
     "Falso. Un cambio nuevo en una sola mama, como un bulto, un hundimiento o una secreción, también debe ser evaluado por un profesional."),
    ("Una persona que ya tuvo cáncer de mama no necesita seguir con controles.", False,
     "Falso. Después de un cáncer de mama se necesitan controles periódicos, según lo indique el equipo de salud que la atiende."),
    ("La autoexploración ayuda a conocer cómo son normalmente tus mamas.", True,
     "Verdadero. Conocer tus mamas te permite notar más fácilmente cualquier cambio y consultar a tiempo."),
    ("Los hombres no necesitan prestar atención a cambios en su pecho.", False,
     "Falso. Aunque es poco frecuente, los hombres también pueden tener cáncer de mama y deben consultar ante un bulto o cambio en el pecho."),
    ("Algunos tipos de terapia hormonal en la menopausia pueden aumentar el riesgo de cáncer de mama.", True,
     "Verdadero. Algunas terapias hormonales se asocian a un mayor riesgo. Su uso debe conversarse con un profesional de salud."),
]

# Sesión 2 (Selección múltiple): (enunciado, explicación, [(opción, es_correcta), ...])
SESION_2 = [
    ("¿Cuál de estos hábitos ayuda a reducir el riesgo de cáncer de mama?",
     "Explicación: La actividad física regular ayuda a mantener un peso saludable y se asocia a un menor riesgo de cáncer de mama.",
     [("A) Mantener actividad física regular", True),
      ("B) Dormir menos de cinco horas", False),
      ("C) Consumir alcohol a diario", False),
      ("D) Evitar los controles médicos", False)]),
    ("¿Qué es la autoexploración mamaria?",
     "Explicación: La autoexploración consiste en observar y palpar tus mamas regularmente para conocerlas y detectar cambios. No reemplaza la mamografía.",
     [("A) Un examen que reemplaza la mamografía", False),
      ("B) Revisar tus propias mamas para conocerlas y notar cambios", True),
      ("C) Un tratamiento para el cáncer de mama", False),
      ("D) Un examen de sangre", False)]),
    ("Si una persona menstrúa, ¿cuándo se recomienda hacer la autoexploración?",
     "Explicación: Unos días después de terminar la menstruación las mamas suelen estar menos sensibles e hinchadas, lo que facilita la revisión.",
     [("A) Durante la menstruación", False),
      ("B) Solo una vez al año", False),
      ("C) Unos días después de terminar la menstruación", True),
      ("D) Nunca, porque no sirve", False)]),
    ("¿Qué examen se usa con frecuencia para complementar la mamografía?",
     "Explicación: La ecografía mamaria usa ultrasonido y suele complementar la mamografía, por ejemplo para estudiar un bulto o en mamas densas.",
     [("A) Radiografía de tórax", False),
      ("B) Electrocardiograma", False),
      ("C) Examen de orina", False),
      ("D) Ecografía mamaria", True)]),
    ("¿Qué significa que una mama sea \"densa\" en la mamografía?",
     "Explicación: Una mama densa tiene más tejido glandular y fibroso que graso. Es frecuente y no es una enfermedad, pero puede dificultar ver algunas lesiones.",
     [("A) Que tiene cáncer", False),
      ("B) Que tiene más tejido glandular y fibroso que graso", True),
      ("C) Que es más grande de lo normal", False),
      ("D) Que está inflamada", False)]),
    ("¿Cuál de estos factores de riesgo NO se puede modificar?",
     "Explicación: La edad es un factor de riesgo que no se puede cambiar. El sedentarismo, el alcohol y el sobrepeso sí se pueden modificar con hábitos saludables.",
     [("A) El sedentarismo", False),
      ("B) La edad", True),
      ("C) El consumo de alcohol", False),
      ("D) El sobrepeso", False)]),
    ("¿Cuál de estos cambios en el pezón requiere consulta médica?",
     "Explicación: Un pezón que se hunde o se retrae de forma nueva puede ser una señal de alerta y debe ser evaluado por un profesional.",
     [("A) Que se endurezca con el frío", False),
      ("B) Que tenga un color distinto al de la piel", False),
      ("C) Que se hunda o se retraiga de forma nueva", True),
      ("D) Que tenga pequeños puntos en la areola que siempre han estado ahí", False)]),
    ("¿Qué genes se asocian a un mayor riesgo hereditario de cáncer de mama?",
     "Explicación: Las alteraciones en los genes BRCA1 y BRCA2 aumentan el riesgo de cáncer de mama y de ovario. Ante antecedentes familiares, un profesional puede orientar sobre estudios genéticos.",
     [("A) BRCA1 y BRCA2", True),
      ("B) Los genes del color de ojos", False),
      ("C) Los genes del grupo sanguíneo", False),
      ("D) Los genes de la estatura", False)]),
]


def agregar_preguntas(apps, schema_editor):

    PreguntaEducativa = apps.get_model('prevencion', 'PreguntaEducativa')
    OpcionRespuesta = apps.get_model('prevencion', 'OpcionRespuesta')

    for sesion, lista in [('S1', SESION_1), ('S3', SESION_3)]:
        for enunciado, verdadero, explicacion in lista:
            PreguntaEducativa.objects.get_or_create(
                sesion=sesion,
                enunciado=enunciado,
                defaults={
                    'respuesta_correcta': verdadero,
                    'explicacion_medica': explicacion,
                }
            )

    for enunciado, explicacion, opciones in SESION_2:
        pregunta, creada = PreguntaEducativa.objects.get_or_create(
            sesion='S2',
            enunciado=enunciado,
            defaults={
                # En la Sesión 2 la respuesta está en las opciones
                'respuesta_correcta': True,
                'explicacion_medica': explicacion,
            }
        )
        if creada:
            for texto, correcta in opciones:
                OpcionRespuesta.objects.create(
                    pregunta=pregunta,
                    texto_opcion=texto,
                    es_correcta=correcta,
                )


class Migration(migrations.Migration):

    dependencies = [
        ('prevencion', '0006_no_guardar_analisis_imagen'),
    ]

    operations = [
        migrations.RunPython(agregar_preguntas, migrations.RunPython.noop),
    ]
