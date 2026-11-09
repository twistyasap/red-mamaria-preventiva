import calendar
import hashlib
from datetime import date, timedelta

from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

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

class Perfil(models.Model):
    usuario = models.OneToOneField(User, on_delete=models.CASCADE, related_name='perfil')
    alias = models.CharField(max_length=50, blank=True, null=True, verbose_name="Alias o Nombre Preferido")

    # Avatar: en vez de una foto (Vercel no puede guardar archivos subidos)
    # se muestra un círculo de color con la inicial. No se guarda nada:
    # la letra y el color se calculan cada vez a partir del usuario.
    # Pares (color claro, color oscuro) para un degradado, todos en la gama
    # morada y rosada de la página para que combinen con el diseño.
    COLORES_AVATAR = [
        ('#a78bfa', '#7c3aed'),   # violeta
        ('#f472b6', '#db2777'),   # rosado
        ('#c084fc', '#9333ea'),   # morado
        ('#818cf8', '#4f46e5'),   # índigo
        ('#fb7185', '#e11d48'),   # frambuesa
        ('#e879f9', '#c026d3'),   # fucsia
        ('#a5b4fc', '#6366f1'),   # lavanda
        ('#f9a8d4', '#ec4899'),   # rosa claro
    ]

    @property
    def nombre_visible(self):
        return self.alias or self.usuario.username

    @property
    def nombre_para_avatar(self):
        # Prioridad: alias -> nombre y apellido -> nombre de usuario
        nombre_completo = f'{self.usuario.first_name} {self.usuario.last_name}'.strip()
        return (self.alias or '').strip() or nombre_completo or self.usuario.username

    @property
    def iniciales(self):
        # - Dos o más palabras: iniciales de las dos primeras ("Diego Mesías" -> "DM")
        # - Una palabra: sus dos primeras letras ("Diego" -> "Di", "yuf" -> "Yu")
        # Solo cuentan letras y números (se ignoran emojis y símbolos).
        palabras = [
            ''.join(c for c in palabra if c.isalnum())
            for palabra in self.nombre_para_avatar.split()
        ]
        palabras = [p for p in palabras if p]

        if len(palabras) >= 2:
            return (palabras[0][0] + palabras[1][0]).upper()
        if palabras:
            palabra = palabras[0]
            return palabra[0].upper() + palabra[1:2].lower()
        return '?'

    @property
    def colores_avatar(self):
        # Siempre los mismos colores para el mismo usuario: se calcula un
        # "resumen" numérico (hash) del nombre de usuario y se usa para
        # elegir uno de los pares de la lista.
        resumen = hashlib.md5(self.usuario.username.encode('utf-8')).hexdigest()
        return self.COLORES_AVATAR[int(resumen, 16) % len(self.COLORES_AVATAR)]

    @property
    def fondo_avatar(self):
        # Degradado CSS listo para usar en style="background: ..."
        claro, oscuro = self.colores_avatar
        return f'linear-gradient(135deg, {claro}, {oscuro})'

    def __str__(self):
        return f"Perfil de {self.usuario.username}"

# Se crea o guarda el perfil automáticamente al registrar o modificar un User
@receiver(post_save, sender=User)
def crear_o_guardar_perfil(sender, instance, created, **kwargs):
    if created:
        Perfil.objects.create(usuario=instance)
    else:
        # Asegura que si el usuario no tenía perfil creado previo a esta actualización, no arroje error
        if hasattr(instance, 'perfil'):
            instance.perfil.save()
        else:
            Perfil.objects.create(usuario=instance)
# Las mamografías analizadas NO se guardan: se procesan en memoria
# (ver prevencion/services/analisis_cnn.py).


# ============================================================
# RECORDATORIOS (calendario de "Mis recordatorios")
# ============================================================
# Solo se guarda lo necesario para mostrar el calendario: qué recordar,
# el día, la hora y si se repite. Al borrar uno, se elimina de verdad.

class Recordatorio(models.Model):
    REPETICIONES = [
        ('una', 'Solo ese día'),
        ('diaria', 'Todos los días'),
        ('semanal', 'Cada semana'),
        ('mensual', 'Cada mes'),
    ]

    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='recordatorios')
    titulo = models.CharField(max_length=120, verbose_name="¿Qué recordar?")
    fecha = models.DateField(verbose_name="Día (o desde cuándo se repite)")
    hora = models.TimeField(verbose_name="Hora")
    repeticion = models.CharField(max_length=10, choices=REPETICIONES, default='una', verbose_name="Repetición")
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['fecha', 'hora']
        verbose_name = "Recordatorio"
        verbose_name_plural = "Recordatorios"

    def __str__(self):
        return f"{self.titulo} ({self.get_repeticion_display()})"

    def ocurrencias(self, desde, hasta):
        """Días entre `desde` (incluido) y `hasta` (excluido) en que toca el recordatorio."""
        inicio = max(self.fecha, desde)
        if inicio >= hasta:
            return []

        if self.repeticion == 'una':
            return [self.fecha] if desde <= self.fecha < hasta else []

        if self.repeticion == 'diaria':
            return [inicio + timedelta(days=i) for i in range((hasta - inicio).days)]

        if self.repeticion == 'semanal':
            # Primer día con el mismo día de la semana que la fecha inicial
            dia = inicio + timedelta(days=(self.fecha.weekday() - inicio.weekday()) % 7)
            dias = []
            while dia < hasta:
                dias.append(dia)
                dia += timedelta(days=7)
            return dias

        # Mensual: el mismo número de día cada mes (si el mes no lo tiene, como
        # el 31 en febrero, ese mes se salta)
        dias = []
        anio, mes = inicio.year, inicio.month
        while date(anio, mes, 1) < hasta:
            if self.fecha.day <= calendar.monthrange(anio, mes)[1]:
                dia = date(anio, mes, self.fecha.day)
                if inicio <= dia < hasta:
                    dias.append(dia)
            anio, mes = (anio + 1, 1) if mes == 12 else (anio, mes + 1)
        return dias


class RecordatorioListo(models.Model):
    """Día en que el usuario marcó un recordatorio como "listo" (ya no aparece como pendiente)."""
    recordatorio = models.ForeignKey(Recordatorio, on_delete=models.CASCADE, related_name='listos')
    fecha = models.DateField()

    class Meta:
        unique_together = ('recordatorio', 'fecha')
        verbose_name = "Recordatorio listo"
        verbose_name_plural = "Recordatorios listos"

    def __str__(self):
        return f"{self.recordatorio.titulo} - {self.fecha}"
