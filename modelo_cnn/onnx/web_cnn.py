"""Versión SIN TensorFlow (la que irá a la web): Pillow + NumPy + onnxruntime."""
import io, json, numpy as np, onnxruntime as ort
from PIL import Image

CFG = json.load(open('config.json'))
H, W = CFG['img_h'], CFG['img_w']
sesion = ort.InferenceSession('modelo_mamografia.onnx', providers=['CPUExecutionProvider'])
pesos = np.load('pesos_cabeza.npy'); W_DENSE, B_DENSE = pesos[:-1], pesos[-1]

def preparar(raw):
    img = Image.open(io.BytesIO(raw))
    if img.mode in ('I;16', 'I;16L', 'I;16B', 'I'):            # PNG 16 bits
        arr = np.asarray(img, dtype=np.float32) / 65535.0
    else:
        if img.format == 'JPEG' and img.mode != 'L':
            img.draft('L', img.size)                         # luminancia directa (como TF)
        arr = np.asarray(img.convert('L'), dtype=np.float32) / 255.0
    arr = np.asarray(Image.fromarray(arr, mode='F').resize((W, H), Image.BILINEAR)) * 255.0
    m = W // 2
    if arr[:, -m:].sum() > arr[:, :m].sum():
        arr = arr[:, ::-1]
    arr = np.clip(np.round(arr), 0, 255)
    return np.repeat(arr[None, :, :, None], 3, axis=-1).astype(np.float32)

def predecir(raw):
    x = preparar(raw)
    act, prob = sesion.run(['activaciones', 'prob_maligno'], {'imagen': x})
    # Grad-CAM: con GAP + Dense, el peso de cada canal es proporcional a W_DENSE
    heat = np.maximum((act[0] * W_DENSE).sum(-1), 0)
    heat = heat / (heat.max() + 1e-8)
    return float(prob[0, 0]), heat, x
