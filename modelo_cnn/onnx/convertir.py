import os, numpy as np
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
import tensorflow as tf, keras, tf2onnx, onnx
from tensorflow.python.framework.convert_to_constants import convert_variables_to_constants_v2

m = keras.models.load_model('modelo_mamografia.keras')
base = m.get_layer('efficientnetb0')
gap, drop, dense = m.get_layer('gap'), m.get_layer('dropout'), m.get_layer('prob_maligno')

@tf.function(input_signature=[tf.TensorSpec([None, 512, 320, 3], tf.float32, name='imagen')])
def f(x):
    feat = base(x, training=False)
    prob = dense(drop(gap(feat), training=False))
    return tf.identity(feat, name='activaciones'), tf.identity(prob, name='prob_maligno')

# Congelar: todos los pesos (incluida la normalización) quedan como constantes
congelada = convert_variables_to_constants_v2(f.get_concrete_function())
gd = congelada.graph.as_graph_def()
salidas = [t.name for t in congelada.outputs]
print('salidas del grafo:', salidas)

onnx_model, _ = tf2onnx.convert.from_graph_def(
    gd, input_names=['imagen:0'], output_names=salidas, opset=17)

# Nombres claros para las salidas
renombres = dict(zip(salidas, ['activaciones', 'prob_maligno']))
for o in onnx_model.graph.output:
    viejo = o.name; o.name = renombres[viejo]
    for n in onnx_model.graph.node:
        n.output[:] = [renombres.get(x, x) for x in n.output]
onnx_model.graph.input[0].name = 'imagen'
for n in onnx_model.graph.node:
    n.input[:] = ['imagen' if x == 'imagen:0' else x for x in n.input]
onnx.checker.check_model(onnx_model)
onnx.save(onnx_model, 'modelo_mamografia.onnx')
print('entradas:', [i.name for i in onnx_model.graph.input], '| salidas:', [o.name for o in onnx_model.graph.output])
print('ONNX guardado:', round(os.path.getsize('modelo_mamografia.onnx') / 1e6, 2), 'MB')

w, b = dense.get_weights()
np.save('pesos_cabeza.npy', np.concatenate([w.ravel(), b.ravel()]).astype('float32'))
