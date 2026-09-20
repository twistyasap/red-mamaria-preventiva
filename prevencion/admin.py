from django.contrib import admin
from .models import PreguntaEducativa, OpcionRespuesta, AnalisisEcografia

class OpcionRespuestaInline(admin.TabularInline):
    model = OpcionRespuesta
    extra = 4  # Muestra 4 alternativas vacías por defecto para llenar rápido (1 correcta y 3 incorrectas)
    max_num = 6
    verbose_name = "Opción para Sesión 2 (Selección Múltiple)"
    verbose_name_plural = "Opciones para Sesión 2 (Selección Múltiple)"

@admin.register(PreguntaEducativa)
class PreguntaEducativaAdmin(admin.ModelAdmin):
    # Columnas que se verán en la lista
    list_display = ('sesion', 'enunciado_corto', 'respuesta_correcta', 'fecha_creacion')
    # Filtros laterales
    list_filter = ('sesion', 'respuesta_correcta')
    # Buscador por texto
    search_fields = ('enunciado', 'explicacion_medica')
    
    # Inyecta las opciones dentro del formulario de la pregunta
    inlines = [OpcionRespuestaInline]

    def enunciado_corto(self, obj):
        return obj.enunciado[:60] + "..." if len(obj.enunciado) > 60 else obj.enunciado
    enunciado_corto.short_description = "Pregunta / Mito"


@admin.register(AnalisisEcografia)
class AnalisisEcografiaAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'porcentaje_riesgo', 'rango_alerta', 'fecha_analisis')
    list_filter = ('rango_alerta', 'fecha_analisis')
    search_fields = ('usuario__username', 'rango_alerta')
    readonly_fields = ('fecha_analisis',)