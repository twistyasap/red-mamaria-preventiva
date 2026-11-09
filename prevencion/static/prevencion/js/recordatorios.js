// Calendario de "Mis recordatorios" (usa la librería FullCalendar)
(function () {
    const modal = document.getElementById('modalRecordatorio');
    const form = document.getElementById('formRecordatorio');
    const campos = {
        tipo: document.getElementById('tipoRecordatorio'),
        otro: document.getElementById('tituloOtro'),
        fecha: document.getElementById('fechaRecordatorio'),
        hora: document.getElementById('horaRecordatorio'),
        minuto: document.getElementById('minutoRecordatorio'),
        ampm: document.getElementById('ampmRecordatorio'),
        repeticion: document.getElementById('repeticionRecordatorio'),
    };
    const error = document.getElementById('errorRecordatorio');
    const acciones = document.getElementById('accionesEdicion');
    let idEditando = null;

    // Minutos 00 a 59 (para poder elegir una hora exacta como 9:37)
    for (let m = 0; m < 60; m++) {
        const texto = String(m).padStart(2, '0');
        campos.minuto.add(new Option(texto, texto));
    }

    // ---------- Conversión entre 24 horas ("14:05") y AM/PM ----------
    function aAmPm(hora24) {
        const [h, m] = hora24.split(':').map(Number);
        return { hora: String(h % 12 || 12), minuto: String(m).padStart(2, '0'), ampm: h < 12 ? 'AM' : 'PM' };
    }

    function a24Horas() {
        let h = Number(campos.hora.value) % 12;
        if (campos.ampm.value === 'PM') h += 12;
        return String(h).padStart(2, '0') + ':' + campos.minuto.value;
    }

    function hoyISO() {
        const d = new Date();
        return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
    }

    // ---------- Ventana ----------
    function actualizarCampos() {
        campos.otro.hidden = campos.tipo.value !== '__otro__';
        document.getElementById('etiquetaFecha').textContent =
            campos.repeticion.value === 'una' ? 'Día' : 'Desde el día';
    }

    function abrirVentana(datos) {
        idEditando = datos.id || null;
        error.hidden = true;

        // Si el texto es una de las opciones de la lista, se selecciona; si no, va en "Otro"
        const esSugerido = [...campos.tipo.options].some(o => o.value === datos.titulo);
        campos.tipo.value = esSugerido ? datos.titulo : (datos.titulo ? '__otro__' : campos.tipo.options[0].value);
        campos.otro.value = esSugerido ? '' : (datos.titulo || '');

        const hora = aAmPm(datos.hora || '09:00');
        campos.hora.value = hora.hora;
        campos.minuto.value = hora.minuto;
        campos.ampm.value = hora.ampm;
        campos.fecha.value = datos.fecha || hoyISO();
        campos.repeticion.value = datos.repeticion || 'una';

        document.getElementById('tituloModalRecordatorio').textContent = idEditando ? 'Editar recordatorio' : 'Nuevo recordatorio';
        acciones.hidden = !idEditando;

        actualizarCampos();
        modal.hidden = false;
        document.addEventListener('keydown', cerrarConEscape);
    }

    function cerrarVentana() {
        modal.hidden = true;
        document.removeEventListener('keydown', cerrarConEscape);
    }

    function cerrarConEscape(e) {
        if (e.key === 'Escape') cerrarVentana();
    }

    function mostrarError(texto) {
        error.textContent = texto;
        error.hidden = false;
    }

    async function enviar(url, datos) {
        const respuesta = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': RECORDATORIOS.csrf },
            body: JSON.stringify(datos || {}),
        });
        const json = await respuesta.json().catch(() => ({}));
        if (!respuesta.ok) throw new Error(json.error || 'No se pudo guardar. Intenta de nuevo.');
        return json;
    }

    campos.tipo.addEventListener('change', function () {
        actualizarCampos();
        if (!campos.otro.hidden) campos.otro.focus();
    });
    campos.repeticion.addEventListener('change', actualizarCampos);

    modal.querySelectorAll('[data-cerrar-recordatorio]').forEach(b => b.addEventListener('click', cerrarVentana));
    modal.addEventListener('click', function (e) {
        if (e.target === modal) cerrarVentana();
    });

    // ---------- Calendario ----------
    const pantallaChica = window.matchMedia('(max-width: 576px)').matches;
    const calendario = new FullCalendar.Calendar(document.getElementById('calendarioRecordatorios'), {
        locale: 'es',
        firstDay: 1,
        height: 'auto',
        initialView: pantallaChica ? 'listMonth' : 'dayGridMonth',
        headerToolbar: { left: 'prev,next', center: 'title', right: 'dayGridMonth,listMonth' },
        buttonText: { month: 'Mes', list: 'Lista' },
        dayMaxEvents: 2,
        eventColor: '#db2777',
        displayEventEnd: false,
        eventTimeFormat: { hour: 'numeric', minute: '2-digit', hour12: true, meridiem: 'short' },
        noEventsContent: 'No tienes recordatorios este mes. Toca "Nuevo recordatorio" para crear uno.',
        events: RECORDATORIOS.eventos,
        dateClick: function (info) {
            abrirVentana({ fecha: info.dateStr });
        },
        eventClick: function (info) {
            abrirVentana(info.event.extendedProps);
        },
    });
    calendario.render();

    document.getElementById('btnNuevoRecordatorio').addEventListener('click', function () {
        abrirVentana({});
    });

    // ---------- Guardar ----------
    form.addEventListener('submit', async function (e) {
        e.preventDefault();
        const titulo = campos.tipo.value === '__otro__' ? campos.otro.value.trim() : campos.tipo.value;
        if (!titulo) return mostrarError('Escribe qué quieres que te recordemos.');
        if (!campos.fecha.value) return mostrarError('Elige un día.');

        const boton = document.getElementById('btnGuardarRecordatorio');
        boton.disabled = true;
        try {
            await enviar(RECORDATORIOS.guardar, {
                id: idEditando,
                titulo: titulo,
                fecha: campos.fecha.value,
                hora: a24Horas(),
                repeticion: campos.repeticion.value,
            });
            cerrarVentana();
            calendario.refetchEvents();
        } catch (err) {
            mostrarError(err.message);
        } finally {
            boton.disabled = false;
        }
    });

    // ---------- Borrar ----------
    document.getElementById('btnBorrarRecordatorio').addEventListener('click', async function () {
        if (!idEditando) return;
        const texto = campos.repeticion.value === 'una'
            ? '¿Borrar este recordatorio?'
            : '¿Borrar este recordatorio? Se borrarán todas sus repeticiones.';
        if (!confirm(texto)) return;
        try {
            await enviar(RECORDATORIOS.borrar.replace('ID', idEditando));
            cerrarVentana();
            calendario.refetchEvents();
        } catch (err) {
            mostrarError(err.message);
        }
    });
})();
