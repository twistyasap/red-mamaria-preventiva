# Modelo CNN de mamografías

La página usa **un solo modelo**, que está en `prevencion/ml/`:

| Archivo | Qué es |
|---|---|
| `prevencion/ml/modelo_mamografia.onnx` | La red (EfficientNetB0) convertida a ONNX para correr en Vercel sin TensorFlow |
| `prevencion/ml/pesos_cabeza.npy` | Pesos de la última capa (para el mapa de calor) |
| `prevencion/ml/config.json` | Umbrales del semáforo y métricas del entrenamiento |
| `prevencion/services/preprocesamiento_v2.py` | Preparación de la imagen (la misma del entrenamiento) |

## Esta carpeta

- **`Clasificador_Mamografias_v2_RSNA.ipynb`**: notebook de Colab que entrenó el modelo de la página (modelo 2, dataset RSNA).
  Test: AUC 0,658 · sensibilidad 88 % · especificidad 27 % (1.143 imágenes).
- **`convertir_onnx.py`**: convierte el `.keras` del notebook a los archivos de `prevencion/ml/`.
  Se ejecuta en un entorno con TensorFlow y tf2onnx, en la misma carpeta que `modelo_mamografia_v2.keras`.
- **`experimentos/Clasificador_Mamografias_v3_RSNA.ipynb`**: modelo 3 (más mamografías sanas por época + regularización).
  Empató con el modelo 2 (AUC 0,659 vs 0,656, diferencia dentro del margen de error) y perdió algo de sensibilidad (85,8 % vs 88 %), por eso **no se usa**.
  El siguiente paso para mejorar sería entrenar con más resolución (1024 px).

Los archivos pesados (`.zip`, `.keras`, `.onnx`, `.npy`) no se suben a GitHub.
El modelo 1 (CBIS-DDSM) quedó en el historial de git y fue reemplazado por el 2.
