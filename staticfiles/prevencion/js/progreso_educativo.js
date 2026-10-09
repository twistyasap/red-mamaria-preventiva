/* ===================================================
   PROGRESO DEL MÓDULO EDUCATIVO
   Se guarda en el navegador (localStorage), separado por
   usuario: dos personas en el mismo computador no se mezclan.

   Formato: { "<id pregunta>": { esCorrecta, opcionSeleccionada } }
   =================================================== */
const ProgresoEducativo = (function () {

    // Clave antigua, compartida entre todos los usuarios del navegador.
    // Se elimina para que las respuestas de otra persona no aparezcan.
    try {
        localStorage.removeItem('respuestas_usuario');
    } catch (e) { /* navegador sin localStorage */ }

    function clave(usuarioId) {
        return 'progreso_educativo_u' + usuarioId;
    }

    function leer(usuarioId) {
        try {
            return JSON.parse(localStorage.getItem(clave(usuarioId)) || '{}');
        } catch (e) {
            return {};
        }
    }

    function guardar(usuarioId, datos) {
        try {
            localStorage.setItem(clave(usuarioId), JSON.stringify(datos));
        } catch (e) { /* sin espacio o sin localStorage: se ignora */ }
    }

    function guardarRespuesta(usuarioId, idPregunta, esCorrecta, opcionSeleccionada) {
        const datos = leer(usuarioId);
        datos[String(idPregunta)] = {
            esCorrecta: esCorrecta,
            opcionSeleccionada: String(opcionSeleccionada)
        };
        guardar(usuarioId, datos);
    }

    // Resumen de una sesión a partir de los ids de sus preguntas
    function resumen(usuarioId, idsPreguntas) {
        const datos = leer(usuarioId);
        let respondidas = 0;
        let correctas = 0;

        idsPreguntas.forEach(function (id) {
            const r = datos[String(id)];
            if (r) {
                respondidas++;
                if (r.esCorrecta) correctas++;
            }
        });

        return {
            total: idsPreguntas.length,
            respondidas: respondidas,
            correctas: correctas,
            completa: idsPreguntas.length > 0 && respondidas === idsPreguntas.length
        };
    }

    // Borra las respuestas de una sesión (para reintentarla)
    function reiniciar(usuarioId, idsPreguntas) {
        const datos = leer(usuarioId);
        idsPreguntas.forEach(function (id) {
            delete datos[String(id)];
        });
        guardar(usuarioId, datos);
    }

    return {
        leer: leer,
        guardarRespuesta: guardarRespuesta,
        resumen: resumen,
        reiniciar: reiniciar
    };
})();
