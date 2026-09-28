"""
Respuestas de respaldo de Sonia.

Se usan solo cuando ningún modelo de Gemini pudo responder (por ejemplo,
cuando Google está saturado), para que el chat nunca quede sin respuesta.
Se busca el tema de la pregunta por palabras clave y se entrega
información general y segura sobre ese tema.
"""

import unicodedata


INTRODUCCION = (
    "En este momento no puedo conectarme con la inteligencia artificial, "
    "pero te dejo información general sobre tu consulta:"
)

CIERRE = (
    "Puedes volver a preguntarme en unos minutos para una respuesta más "
    "completa. Ante cualquier duda sobre tu salud, consulta con un "
    "profesional en tu CESFAM o centro de salud."
)


# Cada tema: palabras clave (sin tildes, en minúscula) y la respuesta.
# El orden importa: se usa el primer tema que coincida.
TEMAS = [
    {
        'palabras': ['hombre', 'hombres', 'masculino', 'varon'],
        'respuesta': (
            "**Cáncer de mama en hombres**\n"
            "- Es poco frecuente, pero **los hombres también pueden "
            "tenerlo**, porque también tienen tejido mamario.\n"
            "- Señales de alerta: un bulto en el pecho, cambios en la piel "
            "o el pezón, o secreción por el pezón.\n"
            "- Ante cualquiera de estos cambios, se recomienda consultar "
            "con un médico."
        ),
    },
    {
        'palabras': ['autoexamen', 'autoexploracion', 'autoobservacion',
                     'palpar', 'palpacion', 'tocarme', 'revisarme',
                     'examinarme', 'reviso', 'revisar'],
        'respuesta': (
            "**Autoexamen de mamas**\n"
            "- Ayuda a **conocer cómo son normalmente tus mamas** para "
            "notar cambios.\n"
            "- Se recomienda hacerlo **una vez al mes**, idealmente unos "
            "días después de la menstruación.\n"
            "- Observa frente al espejo la forma, la piel y los pezones, y "
            "palpa con la yema de los dedos en círculos, incluyendo la "
            "axila.\n"
            "- **No reemplaza la mamografía** ni los controles con un "
            "profesional."
        ),
    },
    {
        'palabras': ['mamografia', 'mamografias', 'radiografia'],
        'respuesta': (
            "**Mamografía**\n"
            "- Es una **radiografía de las mamas** que permite detectar "
            "cambios incluso antes de que se puedan palpar.\n"
            "- Cuándo y cada cuánto hacerla **depende de tu edad y tus "
            "antecedentes**: tu médico o matrona te lo indicará.\n"
            "- En Chile puedes solicitarla en tu **CESFAM**.\n"
            "- Puede ser incómoda por unos segundos debido a la "
            "compresión, pero es un examen rápido."
        ),
    },
    {
        'palabras': ['ecografia', 'ecografias', 'ecomamaria', 'ultrasonido'],
        'respuesta': (
            "**Ecografía mamaria**\n"
            "- Usa ultrasonido (no radiación) para ver el interior de la "
            "mama.\n"
            "- Suele usarse para **complementar la mamografía** o para "
            "revisar un hallazgo específico, como un bulto.\n"
            "- Es el profesional de salud quien indica si es necesaria."
        ),
    },
    {
        'palabras': ['sintoma', 'sintomas', 'senal', 'senales', 'signo',
                     'signos', 'bulto', 'bultos', 'dolor', 'duele',
                     'duelen', 'secrecion',
                     'pezon', 'hundimiento', 'naranja', 'alerta'],
        'respuesta': (
            "**Señales de alerta en las mamas**\n"
            "- Un **bulto** o endurecimiento nuevo en la mama o la axila.\n"
            "- Cambios en la **piel**: hundimientos, enrojecimiento o "
            "aspecto de *piel de naranja*.\n"
            "- Cambios en el **pezón**: hundimiento nuevo o secreción.\n"
            "- Cambios en la forma o el tamaño de la mama.\n"
            "\n"
            "Muchos de estos cambios **no son cáncer**, pero siempre deben "
            "ser evaluados por un profesional de salud."
        ),
    },
    {
        'palabras': ['riesgo', 'riesgos', 'factor', 'factores',
                     'antecedente', 'antecedentes', 'hereditario',
                     'herencia', 'genetica', 'familia', 'familiar'],
        'respuesta': (
            "**Factores de riesgo**\n"
            "- **Edad**: el riesgo aumenta con los años.\n"
            "- **Antecedentes familiares** de cáncer de mama u ovario.\n"
            "- Sedentarismo, sobrepeso y consumo de alcohol.\n"
            "\n"
            "Tener un factor de riesgo **no significa que vayas a tener "
            "cáncer**, y también puede aparecer sin antecedentes. Por eso "
            "son importantes los controles preventivos."
        ),
    },
    {
        'palabras': ['prevenir', 'prevencion', 'evitar', 'habito',
                     'habitos', 'alimentacion', 'ejercicio', 'saludable'],
        'respuesta': (
            "**Prevención y detección temprana**\n"
            "- Mantén una **actividad física regular** y un peso "
            "saludable.\n"
            "- Evita o reduce el consumo de **alcohol** y tabaco.\n"
            "- Realiza el **autoexamen mensual** para conocer tus mamas.\n"
            "- Asiste a tus **controles preventivos** y a la mamografía "
            "cuando te la indiquen.\n"
            "\n"
            "La **detección temprana** aumenta mucho las posibilidades de "
            "un tratamiento exitoso."
        ),
    },
    {
        'palabras': ['cancer', 'mama', 'mamas', 'seno', 'senos', 'tumor',
                     'que es'],
        'respuesta': (
            "**¿Qué es el cáncer de mama?**\n"
            "- Es una enfermedad en la que **células de la mama crecen de "
            "forma descontrolada** y pueden formar un tumor.\n"
            "- Es más frecuente en mujeres, pero también puede afectar a "
            "hombres.\n"
            "- Detectarlo a tiempo, con controles y mamografías, mejora "
            "mucho las posibilidades de tratamiento."
        ),
    },
]

RESPUESTA_GENERAL = (
    "Puedo darte información sobre estos temas:\n"
    "- Autoexamen de mamas\n"
    "- Mamografía y ecografía\n"
    "- Señales de alerta\n"
    "- Factores de riesgo y prevención\n"
    "- Cáncer de mama en hombres"
)


def normalizar(texto):
    """Pasa el texto a minúsculas y sin tildes para comparar palabras."""

    texto = unicodedata.normalize('NFD', texto.lower())

    return ''.join(
        letra for letra in texto
        if unicodedata.category(letra) != 'Mn'
    )


def obtener_respuesta_respaldo(mensaje_usuario):
    """
    Retorna una respuesta general según el tema del mensaje.
    Siempre retorna un texto (nunca falla).
    """

    texto = normalizar(mensaje_usuario)
    palabras = set(
        ''.join(c if c.isalnum() else ' ' for c in texto).split()
    )

    def coincide(clave):
        # Las claves de varias palabras ("que es") se buscan como frase
        if ' ' in clave:
            return clave in texto

        # Palabra exacta, o que empiece con la clave (prevenirlo,
        # senales, hombres...) si la clave es suficientemente larga
        return any(
            palabra == clave
            or (len(clave) >= 5 and palabra.startswith(clave))
            for palabra in palabras
        )

    for tema in TEMAS:
        if any(coincide(clave) for clave in tema['palabras']):
            return f"{INTRODUCCION}\n\n{tema['respuesta']}\n\n{CIERRE}"

    return f"{INTRODUCCION}\n\n{RESPUESTA_GENERAL}\n\n{CIERRE}"
