import os, io, glob, json, numpy as np
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
import tensorflow as tf, keras
from PIL import Image
import web_cnn

# --- imágenes de prueba: panel izquierdo de los Grad-CAM del notebook ---
pruebas = {}
for f in sorted(glob.glob('../nb/celda27_img*.png'))[:12]:
    im = np.asarray(Image.open(f).convert('L'))
    izq = im[:, : im.shape[1] // 2]
    filas = np.where((izq < 250).mean(1) > 0.5)[0]; cols = np.where((izq < 250).mean(0) > 0.5)[0]
    rec = Image.fromarray(izq[filas.min():filas.max(), cols.min():cols.max()])
    b = io.BytesIO(); rec.save(b, 'PNG'); pruebas[os.path.basename(f)] = b.getvalue()
base = Image.open(io.BytesIO(pruebas[sorted(pruebas)[3]]))
def guardar(img, fmt, **kw):
    b = io.BytesIO(); img.save(b, fmt, **kw); return b.getvalue()
pruebas['JPG color'] = guardar(Image.merge('RGB', [base]*3).resize((1200, 1900)), 'JPEG', quality=92)
pruebas['volteada'] = guardar(base.transpose(Image.FLIP_LEFT_RIGHT), 'PNG')
a16 = (np.asarray(base, np.float32) / 255 * 65535).astype(np.uint16)
pruebas['PNG 16 bits'] = guardar(Image.fromarray(a16), 'PNG')
rng = np.random.default_rng(0)
pruebas['foto (no mamografía)'] = guardar(Image.fromarray(rng.integers(0, 255, (600, 800, 3), dtype=np.uint8)), 'JPEG')

# --- referencia: tu preprocesamiento + modelo original de TensorFlow ---
os.chdir('.'); import preprocesamiento as ref
m = keras.models.load_model('modelo_mamografia.keras')
base_m = m.get_layer('efficientnetb0'); cabeza = [m.get_layer(n) for n in ('gap', 'dropout', 'prob_maligno')]

def gradcam_tf(x):   # misma función del notebook (celda 27)
    with tf.GradientTape() as t:
        conv = base_m(x, training=False); t.watch(conv); out = conv
        for c in cabeza: out = c(out, training=False)
        s = out[:, 0]
    g = tf.reduce_mean(t.gradient(s, conv)[0], axis=(0, 1))
    h = tf.nn.relu(tf.reduce_sum(conv[0] * g, -1)); return (h / (tf.reduce_max(h) + 1e-8)).numpy()

print(f"{'imagen':24} {'TF original':>11} {'ONNX+web':>9} {'dif':>8} {'mismo nivel':>11} {'corr GradCAM':>12} {'pix dif max':>11}")
umbral = web_cnn.CFG['umbral']
def nivel(p): return 'Verde' if p < umbral else ('Amarillo' if p < 0.60 else 'Rojo')
difs = []
for n, raw in pruebas.items():
    x_tf = ref.preparar_desde_bytes(raw)
    p_tf = float(m(x_tf, training=False)[0, 0]); h_tf = gradcam_tf(x_tf)
    p_web, h_web, x_web = web_cnn.predecir(raw)
    pix = float(np.abs(x_tf.numpy() - x_web).max())
    corr = np.corrcoef(h_tf.ravel(), h_web.ravel())[0, 1]
    difs.append(abs(p_tf - p_web))
    print(f"{n:24} {p_tf:11.4f} {p_web:9.4f} {abs(p_tf-p_web):8.4f} {str(nivel(p_tf)==nivel(p_web)):>11} {corr:12.4f} {pix:11.0f}")

# --- solo el modelo (misma entrada exacta) ---
x = ref.preparar_desde_bytes(pruebas[sorted(pruebas)[0]]).numpy()
p_k = float(m(x)[0, 0]); p_o = float(web_cnn.sesion.run(['prob_maligno'], {'imagen': x})[0][0, 0])
print(f"\nSolo modelo (misma entrada): Keras={p_k:.6f} ONNX={p_o:.6f} dif={abs(p_k-p_o):.2e}")
print(f"Diferencia máxima de probabilidad de punta a punta: {max(difs):.4f}")
