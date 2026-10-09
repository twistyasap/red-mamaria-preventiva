
# Preprocesamiento del modelo 2 (idéntico en el notebook y en la web).
# Solo NumPy + Pillow.
import numpy as np
from PIL import Image

BASE, IMG_H, IMG_W = 512, 512, 320


def a_gris(imagen):
    # Imagen PIL -> arreglo float32 en 0-1 (acepta 8 y 16 bits, color o gris)
    if imagen.mode in ('I;16', 'I;16L', 'I;16B', 'I'):
        a = np.asarray(imagen, dtype=np.float32)
        return np.clip(a / (65535.0 if a.max() > 255 else 255.0), 0, 1)
    return np.asarray(imagen.convert('L'), dtype=np.float32) / 255.0


def redimensionar(a, ancho, alto):
    return np.asarray(Image.fromarray(a.astype(np.float32), mode='F').resize((ancho, alto), Image.BILINEAR))


def tramo_mas_largo(mascara_1d):
    # Inicio y fin (exclusivo) del tramo de True más largo
    mejor, inicio, mejor_ini = 0, None, 0
    for i, v in enumerate(list(mascara_1d) + [False]):
        if v and inicio is None:
            inicio = i
        elif not v and inicio is not None:
            if i - inicio > mejor:
                mejor, mejor_ini = i - inicio, inicio
            inicio = None
    return (mejor_ini, mejor_ini + mejor) if mejor else None


def limpiar_fuera_de_mama(a, umbral=0.10, hueco=12, inicio_max=0.30, largo_min=0.10):
    # La mama (ya a la izquierda) parte cerca del borde del tórax. En cada fila se conserva
    # solo el TRAMO de tejido más largo que empieza cerca de ese borde. Las etiquetas
    # ('RCC'), marcadores, reglas y barras son tramos cortos o separados: se borran.
    # Huecos oscuros de menos de `hueco` píxeles (zonas de grasa) se consideran tejido.
    alto, ancho = a.shape
    limpia = np.zeros_like(a)
    brillante = a > umbral
    for y in range(alto):
        d = np.diff(np.concatenate(([0], brillante[y].astype(np.int8), [0])))
        inicios, fines = list(np.flatnonzero(d == 1)), list(np.flatnonzero(d == -1))
        if not inicios:
            continue
        tramos = [[inicios[0], fines[0]]]
        for i0, f0 in zip(inicios[1:], fines[1:]):
            if i0 - tramos[-1][1] < hueco:
                tramos[-1][1] = f0            # une tramos separados por un hueco pequeño
            else:
                tramos.append([i0, f0])
        validos = [t for t in tramos if t[0] <= inicio_max * ancho and t[1] - t[0] >= largo_min * ancho]
        if validos:
            x0, x1 = max(validos, key=lambda t: t[1] - t[0])
            limpia[y, x0:x1] = a[y, x0:x1]
    return limpia


def caja_mama(a, umbral=0.08, fraccion=0.02, margen=0.02, minimo=0.25):
    # Caja (y0, y1, x0, x1) de la mama: el bloque brillante más grande.
    # Los textos y marcadores quedan fuera porque son tramos cortos.
    alto, ancho = a.shape
    mascara = a > umbral
    cols = tramo_mas_largo(mascara.mean(axis=0) > fraccion)
    if cols is None:
        return 0, alto, 0, ancho
    x0, x1 = cols
    filas = tramo_mas_largo(mascara[:, x0:x1].mean(axis=1) > fraccion)
    if filas is None:
        return 0, alto, 0, ancho
    y0, y1 = filas
    mx, my = int(margen * ancho), int(margen * alto)
    x0, x1 = max(0, x0 - mx), min(ancho, x1 + mx)
    y0, y1 = max(0, y0 - my), min(alto, y1 + my)
    if (x1 - x0) < minimo * ancho or (y1 - y0) < minimo * alto:
        return 0, alto, 0, ancho      # recorte dudoso: se usa la imagen completa
    return y0, y1, x0, x1


def preparar_imagen(imagen):
    # Imagen PIL -> uint8 (IMG_H, IMG_W) lista para el modelo
    a = redimensionar(a_gris(imagen), BASE, BASE)

    # Imagen invertida (fondo blanco): se invierte solo si así tiene claramente
    # más fondo negro. (El notebook miraba solo el borde, pero muchas películas
    # escaneadas tienen un marco blanco y no están invertidas. En RSNA, con
    # fondo negro, ambos criterios dan lo mismo: el modelo no cambia.)
    if (a < 0.15).mean() < (a > 0.85).mean():
        a = 1.0 - a

    mitad = BASE // 2
    if a[:, mitad:].sum() > a[:, :mitad].sum():   # mama siempre a la izquierda
        a = a[:, ::-1]

    limpia = limpiar_fuera_de_mama(a)
    if (limpia > 0.10).mean() < 0.05:   # limpieza dudosa (casi nada quedó): se usa la imagen tal cual
        limpia = a
    y0, y1, x0, x1 = caja_mama(limpia)
    a = redimensionar(np.ascontiguousarray(limpia[y0:y1, x0:x1]), IMG_W, IMG_H)
    return np.clip(np.round(a * 255.0), 0, 255).astype(np.uint8)


def a_entrada(img_u8):
    # uint8 (H, W) -> float32 (1, H, W, 3) en 0-255 (EfficientNet normaliza internamente)
    return np.repeat(img_u8[None, :, :, None].astype(np.float32), 3, axis=-1)
