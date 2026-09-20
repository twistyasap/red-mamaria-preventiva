from django.db import models
from django.contrib.auth.models import User

# Modelos para las 3 Sesiones Educativas (CRUD)
class PreguntaEducativa(models.Model):
    TIPO_SESION = [
        ('S1', 'Sesión 1: Mitos vs Realidades'),
        ('S2', 'Sesión 2: Preguntas Clave (Selección Múltiple)'),
        ('S3', 'Sesión 3: Verdadero o Falso'),
    ]
    
    sesion = models.CharField(max_length=2, choices=TIPO_SESION, verbose_name="Sesión")
    enunciado = models.TextField(verbose_name="Pregunta o Mito")
    
    # Aplica para Sesión 1 y 3 (Verdadero / Falso - Mito / Realidad)
    respuesta_correcta = models.BooleanField(
        default=True, 
        verbose_name="¿Es Verdadero/Realidad? (Solo Sesión 1 y 3)",
        help_text="Marcar para Verdadero/Realidad. Desmarcar para Falso/Mito."
    )
    
    explicacion_medica = models.TextField(
        help_text="Justificación redactada por el especialista", 
        verbose_name="Explicación Médica"
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Pregunta Educativa"
        verbose_name_plural = "Preguntas Educativas"

    def __str__(self):
        return f"{self.get_sesion_display()} - {self.enunciado[:40]}..."


class OpcionRespuesta(models.Model):
    """
    Opciones de selección múltiple asignadas a la Sesión 2.
    """
    pregunta = models.ForeignKey(
        PreguntaEducativa, 
        on_delete=models.CASCADE, 
        related_name='opciones',
        verbose_name="Pregunta Asociada"
    )
    texto_opcion = models.CharField(max_length=255, verbose_name="Texto de la Opción")
    es_correcta = models.BooleanField(
        default=False, 
        verbose_name="¿Es la respuesta correcta?"
    )

    class Meta:
        verbose_name = "Opción de Respuesta"
        verbose_name_plural = "Opciones de Respuesta"

    def __str__(self):
        estado = "CORRECTA" if self.es_correcta else "INCORRECTA"
        return f"[{estado}] {self.texto_opcion}"


# Modelo para guardar el Análisis de Imagen Médica (Mamografía / Ecografía)
class AnalisisEcografia(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Paciente")
    imagen_original = models.ImageField(upload_to='imagenes_mamarias/', verbose_name="Imagen Mamaria")
    mapa_gradcam = models.ImageField(upload_to='gradcam/', blank=True, null=True, verbose_name="Mapa de Calor (Grad-CAM)")
    porcentaje_riesgo = models.FloatField(verbose_name="Porcentaje de Riesgo (%)")
    rango_alerta = models.CharField(max_length=20, verbose_name="Nivel de Alerta") # Verde, Amarillo, Rojo
    fecha_analisis = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Análisis de Imagen Mamaria"
        verbose_name_plural = "Análisis de Imágenes Mamarias"

    def __str__(self):
        return f"Paciente: {self.usuario.username} - Riesgo: {self.porcentaje_riesgo}%"