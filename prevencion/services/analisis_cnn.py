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


def _a_8_bits(imagen):
    """Copia de la imagen en 8 bits (los PNG de 16 bits quedarían blancos al convertirlos)."""

    muestra = imagen.copy()
    if muestra.mode in ('I;16', 'I;16L', 'I;16B', 'I'):
        valores = np.asarray(muestra, dtype=np.float32) / 65535.0 * 255.0
        muestra = Image.fromarray(np.clip(valores, 0, 255).astype(np.uint8))
    return muestra


def _gris_reducido(imagen):
    """Copia pequeña en escala de grises (0-255) para los filtros rápidos."""

    muestra = _a_8_bits(imagen)
    muestra.thumbnail((256, 256))
    return np.asarray(muestra.convert('RGB'), dtype=np.float32)


def es_imagen_doble(imagen):
    """
    Detecta imágenes con DOS mamas lado a lado (por ejemplo R-MLO y L-MLO
    juntas). El modelo se entrenó con una sola mama por imagen, así que
    estas imágenes deben rechazarse.

    Se usa el canal más brillante para que también funcione con
    mamografías teñidas (azules, etc.). Se mira cuánto tejido hay en cada
    columna de la imagen:
    - Doble con separación: hay una franja vacía en el medio con bastante
      tejido a ambos lados.
    - Doble sin separación: imagen apaisada con el tejido repartido de
      forma pareja entre las dos mitades (una mama sola queda cargada
      hacia un costado).
    """

    gris = _gris_reducido(imagen).max(axis=-1)

    # Fondo claro (mamografía invertida): llevar a fondo oscuro
    borde = np.concatenate([gris[0], gris[-1], gris[:, 0], gris[:, -1]])
    if (borde > 200).mean() > 0.6:
        gris = 255 - gris

    tejido = gris > 40
    ocupacion = tejido.mean(axis=0)
    ancho = len(ocupacion)
    total = ocupacion.sum()

    if total == 0:
        return False

    # 1) Franja vacía entre dos zonas con tejido
    vacia = ocupacion < 0.03
    hay_tejido = ocupacion > 0.10
    x = 0
    while x < ancho:
        if not vacia[x]:
            x += 1
            continue
        inicio = x
        while x < ancho and vacia[x]:
            x += 1
        fin = x  # franja vacía: columnas [inicio, fin)

        izq, der = ocupacion[:inicio], ocupacion[fin:]
        if (
            izq.sum() >= 0.25 * total
            and der.sum() >= 0.25 * total
            and hay_tejido[:inicio].sum() >= 0.15 * ancho
            and hay_tejido[fin:].sum() >= 0.15 * ancho
        ):
            return True

    # 2) Apaisada y con el tejido parejo en ambas mitades (umbral más
    #    bajo: con el borde de la mama incluido se reparte mejor)
    alto = gris.shape[0]
    mitad = ancho // 2
    ocupacion = (gris > 15).mean(axis=0)
    izq, der = ocupacion[:mitad].mean(), ocupacion[mitad:].mean()
    return (
        ancho >= 1.3 * alto
        and min(izq, der) >= 0.25
        and max(izq, der) / min(izq, der) <= 1.6
    )


def parece_mamografia(imagen, es_parte=False):
    """
    Filtro básico para rechazar imágenes que claramente no son una
    mamografía (fotos a color, documentos, imágenes en blanco, etc.).

    Una mamografía es gris, tiene mucho fondo negro y la mama está
    pegada a uno de los costados. Calibrado con las mamografías del
    notebook y con fotos, logos, documentos e imágenes de ruido.

    es_parte: la imagen es una parte recortada de un collage (ver
    separar_vistas), que se revisa con límites algo más amplios.
    """

    limite_color = LIMITE_COLOR_PARTE if es_parte else 8
    asimetria_minima = ASIMETRIA_MINIMA_PARTE if es_parte else 1.3

    a = _gris_reducido(imagen)

    color = (
        np.abs(a[..., 0] - a[..., 1])
        + np.abs(a[..., 1] - a[..., 2])
        + np.abs(a[..., 0] - a[..., 2])
    ).mean() / 3

    if color > limite_color:
        return False

    gris = a.mean(axis=-1)

    # Se prueba la imagen tal cual y también invertida (mamografías con
    # fondo blanco). No basta con mirar el borde: muchas películas
    # escaneadas tienen un marco blanco y son mamografías normales.
    return (
        _forma_de_mamografia(gris, asimetria_minima)
        or _forma_de_mamografia(255 - gris, asimetria_minima)
    )


def _forma_de_mamografia(gris, asimetria_minima):
    """Mucho fondo oscuro, mama pegada a un costado y poco ruido."""

    fondo_oscuro = (gris < 40).mean()

    mitad = gris.shape[1] // 2
    izquierda, derecha = gris[:, :mitad].mean(), gris[:, mitad:].mean()
    asimetria = max(izquierda, derecha) / (min(izquierda, derecha) + 1)

    ruido = np.abs(np.diff(gris, axis=1)).mean()

    return (
        0.15 <= fondo_oscuro <= 0.95
        and asimetria >= asimetria_minima
        and ruido <= 10
    )


# ============================================================
# 1b. IMÁGENES CON VARIAS VISTAS JUNTAS
# ============================================================
# Algunos exámenes vienen como una sola imagen con 2 o 4 vistas (ambas
# mamas, de frente y de lado), separadas por líneas blancas o franjas
# negras. El modelo se entrenó con UNA mama por imagen, así que la imagen
# se corta en sus partes y cada una se analiza por separado.

LADO_SEPARAR = 800          # se buscan los cortes en una copia chica
PARTE_MINIMA = 0.15         # cada parte ocupa al menos el 15 % del ancho/alto
LADO_MINIMO_PARTE = 120     # las partes de un collage suelen ser chicas
# Los collages suelen ser fotos de la placa con un leve tinte de color:
# se tolera un poco más (mamografías probadas: hasta 8,1; fotos a color: desde 14)
LIMITE_COLOR_PARTE = 11
# Al recortar, a la parte le queda poco fondo negro y la mama ya no se ve tan
# cargada a un costado (la LCC de un examen típico daba 1,25)
ASIMETRIA_MINIMA_PARTE = 1.15


def _partes_en_eje(gris, eje):
    """
    Busca, a lo largo de un eje (0 = columnas, 1 = filas), los tramos con
    mama separados por líneas claras o franjas negras. Retorna una lista
    de (inicio, fin) en proporción 0-1; si no hay división, un solo tramo.
    """

    linea_clara = (gris > 190).mean(axis=eje) >= 0.80
    franja_negra = (gris > 40).mean(axis=eje) <= 0.01
    separador = linea_clara | franja_negra

    largo = len(separador)
    tramos, inicio = [], None
    for i, es_separador in enumerate(list(separador) + [True]):
        if not es_separador and inicio is None:
            inicio = i
        elif es_separador and inicio is not None:
            tramos.append((inicio, i))
            inicio = None

    # Solo cuentan los tramos anchos y con bastante tejido: así una
    # etiqueta ("RCC") o un marco no se toman como otra mama
    def con_mama(ini, fin):
        bloque = gris[:, ini:fin] if eje == 0 else gris[ini:fin, :]
        return (fin - ini) >= PARTE_MINIMA * largo and (bloque > 40).mean() >= 0.15

    validos = [(ini / largo, fin / largo) for ini, fin in tramos if con_mama(ini, fin)]
    return validos if len(validos) > 1 else [(0.0, 1.0)]


def separar_vistas(imagen):
    """
    Retorna la lista de partes de la imagen como pares (imagen PIL, fila):
    una mamografía normal devuelve [(imagen, 0)]; un collage de 4 vistas
    en 2x2 devuelve 4 partes, 2 en la fila 0 y 2 en la fila 1.
    """

    chica = _a_8_bits(imagen).convert('L')
    chica.thumbnail((LADO_SEPARAR, LADO_SEPARAR))
    gris = np.asarray(chica, dtype=np.float32)

    cajas = []
    for x0, x1 in _partes_en_eje(gris, 0):
        columna = gris[:, int(x0 * gris.shape[1]):int(x1 * gris.shape[1])]
        for y0, y1 in _partes_en_eje(columna, 1):
            cajas.append((x0, y0, x1, y1))

    if len(cajas) == 1:
        return [(imagen, 0)]

    # Orden de lectura: de arriba hacia abajo y de izquierda a derecha
    cajas.sort(key=lambda c: (round(c[1], 1), c[0]))
    filas = sorted({round(c[1], 1) for c in cajas})

    ancho, alto = imagen.size
    return [
        (
            imagen.crop((round(x0 * ancho), round(y0 * alto), round(x1 * ancho), round(y1 * alto))),
            filas.index(round(y0, 1)),
        )
        for x0, y0, x1, y1 in cajas
    ]


# ============================================================
# 1c. ¿QUÉ VISTA ES? (RCC, LCC, RMLO, LMLO)
# ============================================================
# Un examen completo tiene 4 vistas, 2 por mama:
# - Lado: en las mamografías digitales, la pared del tórax queda a la
#   derecha de la imagen en la mama derecha (R) y a la izquierda en la
#   mama izquierda (L).
# - Tipo: la vista oblicua (MLO) muestra el músculo pectoral, un triángulo
#   claro en la esquina de arriba junto al tórax; la cráneo-caudal (CC) no.
# Es una ESTIMACIÓN (probada: tipo 38/40 en películas CBIS; lado correcto en
# mamografías digitales, pero algunas películas escaneadas vienen volteadas).

VISTAS = {
    'RCC': ('derecha', 'Cráneo-caudal (CC)'),
    'LCC': ('izquierda', 'Cráneo-caudal (CC)'),
    'RMLO': ('derecha', 'Medio-lateral oblicua (MLO)'),
    'LMLO': ('izquierda', 'Medio-lateral oblicua (MLO)'),
}
UMBRAL_PECTORAL = 1.2   # bajo esto CC, desde esto MLO


def rasgos_vista(imagen):
    """Retorna (lado 'R' | 'L', índice del músculo pectoral)."""

    pv = preprocesamiento_v2
    a = pv.redimensionar(pv.a_gris(imagen), 256, 256)
    if (a < 0.15).mean() < (a > 0.85).mean():
        a = 1.0 - a

    # La pared del tórax está en la mitad con más tejido
    lado = 'R' if a[:, 128:].sum() > a[:, :128].sum() else 'L'
    if lado == 'R':
        a = a[:, ::-1]      # tórax siempre a la izquierda

    limpia = pv.limpiar_fuera_de_mama(a)
    if (limpia > 0.10).mean() < 0.05:
        limpia = a
    y0, y1, x0, x1 = pv.caja_mama(limpia)
    mama = limpia[y0:y1, x0:x1]
    alto, ancho = mama.shape

    # Brillo de la esquina de arriba junto al tórax, comparado con el tejido
    # del centro de la mama: el músculo pectoral es mucho más claro
    esquina = mama[:int(0.25 * alto), :int(0.25 * ancho)]
    centro = mama[int(0.40 * alto):int(0.75 * alto), :int(0.50 * ancho)]
    esquina, centro = esquina[esquina > 0.1], centro[centro > 0.1]
    if not esquina.size or not centro.size:
        return lado, 0.0
    return lado, float(esquina.mean() / centro.mean())


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
    # El color se pinta solo donde el modelo miró con más atención; el resto
    # de la mamografía queda en gris, sin el tinte azul por encima
    opacidad = (0.55 * np.clip((calor - 0.25) / 0.5, 0, 1))[..., None]
    mezcla = (1 - opacidad) * base + opacidad * _colormap_jet(calor)
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


MAXIMO_IMAGENES = 4         # imágenes por envío
MAXIMO_VISTAS = 8           # partes analizadas en total (4 imágenes con collages)

MENSAJE_NO_ES_MAMOGRAFIA = (
    'La imagen no parece una mamografía. Sube la imagen de tu '
    'examen de mamografía (en escala de grises, tal como la '
    'entrega el centro de salud).'
)
MENSAJE_DOS_MAMAS = (
    'Aquí hay dos mamas juntas y no pudimos separarlas. Recorta la '
    'imagen y sube cada mama por separado.'
)
ORDEN_NIVELES = ['Verde', 'Amarillo', 'Rojo']


def analizar_vista(imagen):
    """
    Analiza UNA mama (imagen PIL ya validada).

    Retorna un dict con: probabilidad (0-1), porcentaje (0-100),
    nivel ('Verde' | 'Amarillo' | 'Rojo') y mapa_calor (data URI).
    """

    entrada, recortada = preparar(imagen)

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


def _nombrar_vistas(analizadas):
    """
    Agrega a cada vista analizada de UNA imagen su código ('RCC', 'LMLO'...),
    su mama ('derecha' / 'izquierda') y el nombre de la vista.

    En un collage con varias filas (lo típico: CC arriba, MLO abajo), todas
    las vistas de una fila son del mismo tipo, así que el tipo se decide
    con el promedio de la fila: es más seguro que mirar cada vista sola.
    """

    por_fila = {}
    for vista in analizadas:
        por_fila.setdefault(vista['fila'], []).append(vista['pectoral'])
    varias_filas = len(por_fila) > 1

    for vista in analizadas:
        pectoral = (
            sum(por_fila[vista['fila']]) / len(por_fila[vista['fila']])
            if varias_filas else vista['pectoral']
        )
        codigo = vista['lado'] + ('MLO' if pectoral >= UMBRAL_PECTORAL else 'CC')
        vista['codigo'] = codigo
        vista['mama'], vista['nombre_vista'] = VISTAS[codigo]


def analizar_mamografias(contenidos):
    """
    Analiza una o varias imágenes subidas (bytes). Si una imagen trae
    varias vistas juntas, se separa y cada parte se analiza aparte.

    Retorna un dict con:
    - vistas: lista de resultados; cada uno con 'origen' y, si se pudo
      analizar, lo mismo que analizar_vista() + la vista estimada
      ('codigo', 'mama', 'nombre_vista'); si no, 'error' con el motivo
    - nivel: el nivel más alto entre las vistas analizadas
    - conteo: cuántas vistas quedaron en cada nivel
    - mamas: resumen por mama (ver _resumen_por_mama)
    Lanza ImagenNoValida si ninguna vista se pudo analizar.
    """

    if len(contenidos) > MAXIMO_IMAGENES:
        raise ImagenNoValida(f'Puedes subir como máximo {MAXIMO_IMAGENES} imágenes a la vez.')

    vistas = []
    for numero, contenido in enumerate(contenidos, 1):
        origen = f'Imagen {numero}' if len(contenidos) > 1 else 'Tu imagen'
        try:
            imagen = leer_imagen(contenido)
        except ImagenNoValida as e:
            vistas.append({'origen': origen, 'error': str(e)})
            continue

        partes = separar_vistas(imagen)
        de_esta_imagen = []
        for parte_numero, (parte, fila) in enumerate(partes, 1):
            texto = origen if len(partes) == 1 else f'{origen} · parte {parte_numero} de {len(partes)}'
            if len(vistas) + len(de_esta_imagen) >= MAXIMO_VISTAS:
                break
            if min(parte.size) < LADO_MINIMO_PARTE:
                de_esta_imagen.append({'origen': texto, 'error': 'Esta parte es muy pequeña para analizarla.'})
            elif es_imagen_doble(parte):
                # Dos mamas pegadas, sin una línea o franja que permita separarlas
                de_esta_imagen.append({'origen': texto, 'error': MENSAJE_DOS_MAMAS})
            elif not parece_mamografia(parte, es_parte=len(partes) > 1):
                de_esta_imagen.append({'origen': texto, 'error': MENSAJE_NO_ES_MAMOGRAFIA})
            else:
                resultado = analizar_vista(parte)
                resultado['origen'] = texto
                resultado['lado'], resultado['pectoral'] = rasgos_vista(parte)
                resultado['fila'] = fila
                de_esta_imagen.append(resultado)

        _nombrar_vistas([v for v in de_esta_imagen if 'error' not in v])

        # Si ninguna parte resultó ser una mama, la imagen completa no es una
        # mamografía: se muestra un solo aviso en vez de uno por parte
        if all(v.get('error') not in (None, MENSAJE_DOS_MAMAS) for v in de_esta_imagen):
            de_esta_imagen = [{'origen': origen, 'error': MENSAJE_NO_ES_MAMOGRAFIA}]
        vistas.extend(de_esta_imagen)

    analizadas = [v for v in vistas if 'error' not in v]
    if not analizadas:
        # Con una sola imagen se muestra su motivo tal cual
        if len(vistas) == 1:
            raise ImagenNoValida(vistas[0]['error'])
        raise ImagenNoValida(
            'No pudimos analizar ninguna de las imágenes. Revisa que sean '
            'mamografías en JPG o PNG, idealmente una vista por imagen.'
        )

    for numero, vista in enumerate(vistas, 1):
        vista['numero'] = numero

    return {
        'vistas': vistas,
        'nivel': max((v['nivel'] for v in analizadas), key=ORDEN_NIVELES.index),
        'conteo': {n: sum(v['nivel'] == n for v in analizadas) for n in ORDEN_NIVELES},
        'analizadas': len(analizadas),
        'una_vista': len(vistas) == 1,
        'mamas': _resumen_por_mama(analizadas),
    }


def _resumen_por_mama(analizadas):
    """
    Agrupa las vistas por mama: [{'titulo': 'Mama derecha', 'nivel': el más
    alto de sus vistas (o None si no hay), 'vistas': [{tipo, porcentaje,
    nivel}], primero la CC y luego la MLO}, ...]
    """

    resumen = []
    for mama in ('derecha', 'izquierda'):
        suyas = sorted(
            (v for v in analizadas if v['mama'] == mama),
            key=lambda v: (v['codigo'].endswith('MLO'), v['numero'])
        )
        resumen.append({
            'titulo': f'Mama {mama}',
            'nivel': max((v['nivel'] for v in suyas), key=ORDEN_NIVELES.index) if suyas else None,
            'vistas': [
                {'tipo': v['codigo'][1:], 'porcentaje': v['porcentaje'], 'nivel': v['nivel']}
                for v in suyas
            ],
        })
    return resumen
