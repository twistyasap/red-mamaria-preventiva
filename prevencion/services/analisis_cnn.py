"""
Análisis de mamografías con la CNN (modelo 2: EfficientNetB0 entrenada con
mamografías digitales de RSNA, pregunta "sana / requiere evaluación").

El modelo se entrenó en Google Colab con TensorFlow y se convirtió a ONNX
(ver modelo_cnn_v2/), para poder ejecutarlo en Vercel sin TensorFlow.
El preprocesamiento (preprocesamiento_v2.py) es el MISMO archivo que generó
el notebook de entrenamiento: recorta la mama y quita etiquetas y marcadores.

Todo ocurre en memoria: la imagen subida NO se guarda en ningún lado.
"""

import base64
import io
import json
from pathlib import Path

import numpy as np
from PIL import Image

from . import preprocesamiento_v2


CARPETA_MODELO = Path(__file__).resolve().parent.parent / 'ml'

with open(CARPETA_MODELO / 'config.json', encoding='utf-8') as archivo:
    CONFIG = json.load(archivo)

ALTO, ANCHO = CONFIG['img_h'], CONFIG['img_w']

# Semáforo (umbrales elegidos en validación, ver config.json):
# - bajo UMBRAL_AMARILLO es Verde (se detecta ~85 % de los cánceres)
# - desde UMBRAL_ROJO es Rojo (solo ~5 % de las sanas llega a Rojo)
UMBRAL_AMARILLO = CONFIG['umbral']
UMBRAL_ROJO = CONFIG.get('umbral_rojo', 0.60)

FORMATOS_PERMITIDOS = {'JPEG', 'PNG'}
TAMANO_MAXIMO_BYTES = 15 * 1024 * 1024
LADO_MINIMO = 200

# Evita "bombas de descompresión" (imágenes diminutas en disco que
# ocupan gigas al abrirse)
Image.MAX_IMAGE_PIXELS = 60_000_000


class ImagenNoValida(Exception):
    """La imagen no se puede analizar. El mensaje se muestra al usuario."""


# ============================================================
# MODELO (se carga una sola vez, la primera vez que se usa)
# ============================================================

_sesion = None
_pesos_cabeza = None


def _cargar_modelo():
    global _sesion, _pesos_cabeza

    if _sesion is None:
        import onnxruntime

        _sesion = onnxruntime.InferenceSession(
            str(CARPETA_MODELO / 'modelo_mamografia.onnx'),
            providers=['CPUExecutionProvider']
        )

        # Pesos de la capa final: [1280 pesos..., sesgo]
        _pesos_cabeza = np.load(CARPETA_MODELO / 'pesos_cabeza.npy')[:-1]

    return _sesion, _pesos_cabeza


# ============================================================
# 1. LEER Y VALIDAR LA IMAGEN
# ============================================================

def leer_imagen(contenido):
    """Abre la imagen subida y verifica que sea un JPG/PNG válido."""

    if len(contenido) > TAMANO_MAXIMO_BYTES:
        raise ImagenNoValida(
            'La imagen es demasiado grande (máximo 15 MB).'
        )

    try:
        # verify() detecta archivos dañados, pero deja la imagen
        # inutilizable, así que luego se vuelve a abrir.
        Image.open(io.BytesIO(contenido)).verify()
        imagen = Image.open(io.BytesIO(contenido))
    except Exception:
        raise ImagenNoValida(
            'No pudimos abrir el archivo. Asegúrate de subir una imagen '
            'JPG o PNG.'
        )

    if imagen.format not in FORMATOS_PERMITIDOS:
        raise ImagenNoValida(
            'Formato no permitido. Sube tu mamografía en JPG o PNG.'
        )

    if min(imagen.size) < LADO_MINIMO:
        raise ImagenNoValida(
            'La imagen es muy pequeña. Sube la mamografía con mejor '
            'resolución.'
        )

    return imagen


def parece_mamografia(imagen):
    """
    Filtro básico para rechazar imágenes que claramente no son una
    mamografía (fotos a color, documentos, imágenes en blanco, etc.).

    Una mamografía es gris, tiene mucho fondo negro y la mama está
    pegada a uno de los costados. Calibrado con las mamografías del
    notebook y con fotos, logos, documentos e imágenes de ruido.
    """

    muestra = imagen.copy()

    # PNG de 16 bits: pasar a 8 bits (si no, al convertir queda blanca)
    if muestra.mode in ('I;16', 'I;16L', 'I;16B', 'I'):
        valores = np.asarray(muestra, dtype=np.float32) / 65535.0 * 255.0
        muestra = Image.fromarray(np.clip(valores, 0, 255).astype(np.uint8))

    muestra.thumbnail((256, 256))
    a = np.asarray(muestra.convert('RGB'), dtype=np.float32)

    color = (
        np.abs(a[..., 0] - a[..., 1])
        + np.abs(a[..., 1] - a[..., 2])
        + np.abs(a[..., 0] - a[..., 2])
    ).mean() / 3

    if color > 8:
        return False

    gris = a.mean(axis=-1)

    # Se prueba la imagen tal cual y también invertida (mamografías con
    # fondo blanco). No basta con mirar el borde: muchas películas
    # escaneadas tienen un marco blanco y son mamografías normales.
    return _forma_de_mamografia(gris) or _forma_de_mamografia(255 - gris)


def _forma_de_mamografia(gris):
    """Mucho fondo oscuro, mama pegada a un costado y poco ruido."""

    fondo_oscuro = (gris < 40).mean()

    mitad = gris.shape[1] // 2
    izquierda, derecha = gris[:, :mitad].mean(), gris[:, mitad:].mean()
    asimetria = max(izquierda, derecha) / (min(izquierda, derecha) + 1)

    ruido = np.abs(np.diff(gris, axis=1)).mean()

    return (
        0.15 <= fondo_oscuro <= 0.95
        and asimetria >= 1.3
        and ruido <= 10
    )


# ============================================================
# 2. PREPROCESAMIENTO (el mismo archivo del notebook 2)
# ============================================================

def preparar(imagen):
    """
    Escala de grises -> 512x512 -> invertir si el fondo es claro -> mama a la
    izquierda -> borrar lo que no es mama -> recorte -> 512x320.
    Retorna (entrada del modelo, imagen recortada uint8 para mostrar).
    """

    recortada = preprocesamiento_v2.preparar_imagen(imagen)
    return preprocesamiento_v2.a_entrada(recortada), recortada


# ============================================================
# 3. MAPA DE CALOR (Grad-CAM)
# ============================================================

def _colormap_jet(valores):
    """Convierte valores 0-1 en colores (azul -> verde -> amarillo -> rojo)."""

    v = np.clip(valores, 0, 1)
    rojo = np.clip(1.5 - np.abs(4 * v - 3), 0, 1)
    verde = np.clip(1.5 - np.abs(4 * v - 2), 0, 1)
    azul = np.clip(1.5 - np.abs(4 * v - 1), 0, 1)

    return np.stack([rojo, verde, azul], axis=-1)


def generar_mapa_calor(recortada, activaciones, pesos):
    """
    Grad-CAM: con la arquitectura del modelo (GAP + una neurona), el peso
    de cada canal es proporcional al peso de la capa final, así que se
    calcula sin gradientes (verificado contra el Grad-CAM del notebook).

    Se dibuja sobre la mama recortada, tal como la vio el modelo.
    Retorna la imagen como data URI PNG (no se guarda).
    """

    calor = np.maximum((activaciones[0] * pesos).sum(axis=-1), 0)
    calor = calor / (calor.max() + 1e-8)
    calor = np.asarray(
        Image.fromarray(calor.astype(np.float32), mode='F').resize(
            (ANCHO, ALTO), Image.BILINEAR
        )
    )

    gris = recortada.astype(np.float32) / 255.0
    base = np.repeat(gris[..., None], 3, axis=-1)
    mezcla = (1 - 0.4) * base + 0.4 * _colormap_jet(calor)
    mezcla = Image.fromarray((np.clip(mezcla, 0, 1) * 255).astype(np.uint8))
    mezcla = mezcla.resize((300, 480), Image.BILINEAR)

    buffer = io.BytesIO()
    mezcla.save(buffer, format='PNG', optimize=True)

    return 'data:image/png;base64,' + base64.b64encode(
        buffer.getvalue()
    ).decode('ascii')


# ============================================================
# 4. ANÁLISIS COMPLETO
# ============================================================

def nivel_semaforo(probabilidad):
    if probabilidad < UMBRAL_AMARILLO:
        return 'Verde'
    if probabilidad < UMBRAL_ROJO:
        return 'Amarillo'
    return 'Rojo'


def analizar_mamografia(contenido):
    """
    Analiza los bytes de una imagen subida.

    Retorna un dict con: probabilidad (0-1), porcentaje (0-100),
    nivel ('Verde' | 'Amarillo' | 'Rojo') y mapa_calor (data URI).
    Lanza ImagenNoValida si la imagen no se puede analizar.
    """

    imagen = leer_imagen(contenido)

    if not parece_mamografia(imagen):
        raise ImagenNoValida(
            'La imagen no parece una mamografía. Sube la imagen de tu '
            'examen de mamografía (en escala de grises, tal como la '
            'entrega el centro de salud).'
        )

    entrada, recortada = preparar(Image.open(io.BytesIO(contenido)))

    sesion, pesos = _cargar_modelo()
    activaciones, probabilidad = sesion.run(
        ['activaciones', 'prob_maligno'],
        {'imagen': entrada}
    )
    probabilidad = float(probabilidad[0, 0])

    return {
        'probabilidad': probabilidad,
        'porcentaje': round(probabilidad * 100),
        'nivel': nivel_semaforo(probabilidad),
        'mapa_calor': generar_mapa_calor(recortada, activaciones, pesos),
    }
