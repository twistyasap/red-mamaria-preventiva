document.addEventListener("DOMContentLoaded", function () {

    // =========================
    // ELEMENTOS DEL CHAT
    // =========================

    const toggleBtn = document.getElementById("toggleChatBtn");
    const closeBtn = document.getElementById("closeChatBtn");
    const chatBox = document.getElementById("chatWidgetBox");
    const form = document.getElementById("chatForm");
    const input = document.getElementById("chatInput");
    const messages = document.getElementById("chatMessages");
    const typingIndicator = document.getElementById("typingIndicator");

    // =========================
    // ABRIR / CERRAR CHAT
    // =========================

    if (toggleBtn && chatBox) {
        toggleBtn.addEventListener("click", function () {

            chatBox.classList.toggle("is-open");

            if (chatBox.classList.contains("is-open") && input) {
                input.focus();
            }

        });
    }

    if (closeBtn && chatBox) {
        closeBtn.addEventListener("click", function () {
            chatBox.classList.remove("is-open");
        });
    }

    // =========================
    // FORMATO DE RESPUESTAS
    // (Markdown básico de Gemini)
    // =========================

    // Se escapa todo el HTML primero, así el texto de la IA
    // nunca puede inyectar etiquetas en la página.
    function escaparHTML(texto) {
        return texto
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#39;");
    }

    // **negrita** y *cursiva* dentro de una línea
    function formatoEnLinea(texto) {
        return texto
            .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
            .replace(/(^|[^*\w])\*(?!\s)([^*]+?)\*(?!\*)/g, "$1<em>$2</em>");
    }

    // Convierte el texto en párrafos y listas (con viñetas o numeradas)
    function formatearMarkdown(texto) {

        const lineas = escaparHTML(texto).split(/\r?\n/);
        const html = [];
        let listaAbierta = null; // "ul", "ol" o null

        function cerrarLista() {
            if (listaAbierta) {
                html.push("</" + listaAbierta + ">");
                listaAbierta = null;
            }
        }

        lineas.forEach(function (linea) {

            const limpia = linea.trim();
            const vineta = limpia.match(/^[*\-•]\s+(.*)$/);
            const numero = limpia.match(/^\d+[.)]\s+(.*)$/);
            const titulo = limpia.match(/^#{1,6}\s+(.*)$/);

            if (vineta || numero) {

                const tipoLista = vineta ? "ul" : "ol";

                if (listaAbierta !== tipoLista) {
                    cerrarLista();
                    html.push("<" + tipoLista + ">");
                    listaAbierta = tipoLista;
                }

                html.push(
                    "<li>" + formatoEnLinea((vineta || numero)[1]) + "</li>"
                );
                return;
            }

            cerrarLista();

            if (!limpia) {
                return;
            }

            if (titulo) {
                html.push("<p><strong>" + formatoEnLinea(titulo[1]) + "</strong></p>");
                return;
            }

            html.push("<p>" + formatoEnLinea(limpia) + "</p>");
        });

        cerrarLista();

        return html.join("");
    }

    // =========================
    // AGREGAR MENSAJES AL CHAT
    // =========================

    function agregarMensaje(texto, tipo) {

        if (!messages) {
            return;
        }

        const div = document.createElement("div");

        div.className =
            "msg " +
            (tipo === "usuario" ? "msg-usuario" : "msg-sonia");

        // Solo las respuestas de Sonia llevan formato;
        // lo que escribe el usuario se muestra tal cual.
        if (tipo === "usuario") {
            div.textContent = texto;
        } else {
            div.innerHTML = formatearMarkdown(texto);
        }

        messages.appendChild(div);

        messages.scrollTop = messages.scrollHeight;

        return div;
    }

    // =========================
    // MOSTRAR / OCULTAR
    // INDICADOR ESCRIBIENDO
    // =========================

    function mostrarEscribiendo() {

        if (typingIndicator) {
            typingIndicator.style.display = "block";
        }

        if (messages) {
            messages.scrollTop = messages.scrollHeight;
        }
    }

    function ocultarEscribiendo() {

        if (typingIndicator) {
            typingIndicator.style.display = "none";
        }
    }

    // =========================
    // BLOQUEAR INPUT MIENTRAS
    // GEMINI RESPONDE
    // =========================

    function bloquearChat(bloqueado) {

        if (input) {
            input.disabled = bloqueado;
        }

        if (form) {
            const botonEnviar = form.querySelector(
                'button[type="submit"]'
            );

            if (botonEnviar) {
                botonEnviar.disabled = bloqueado;
            }
        }
    }

    // =========================
    // AVISO DE MENSAJE VACÍO
    // =========================

    let avisoVacio = null;
    let temporizadorAviso = null;

    function mostrarAvisoVacio() {

        if (!avisoVacio) {
            avisoVacio = document.createElement("div");
            avisoVacio.className = "chat-aviso-vacio";
            avisoVacio.setAttribute("role", "alert");
            avisoVacio.textContent =
                "No has escrito nada a nuestra asistente, " +
                "escribe algo y te atenderemos.";
            form.insertAdjacentElement("beforebegin", avisoVacio);
        }

        avisoVacio.hidden = false;
        input.focus();

        clearTimeout(temporizadorAviso);
        temporizadorAviso = setTimeout(ocultarAvisoVacio, 4000);
    }

    function ocultarAvisoVacio() {
        if (avisoVacio) {
            avisoVacio.hidden = true;
        }
    }

    if (input) {
        input.addEventListener("input", ocultarAvisoVacio);
    }

    // =========================
    // MEMORIA DE LA CONVERSACIÓN
    // Se envía a Sonia junto con cada mensaje nuevo para que
    // recuerde lo que se habló. Se borra al recargar la página.
    // =========================

    const historial = [];
    const MAX_HISTORIAL = 10;

    // =========================
    // PEDIR RESPUESTA A SONIA
    // =========================

    // Si Google está saturado, el chat espera un poco y vuelve a
    // intentar solo una vez antes de mostrar el error.
    const REINTENTOS_AUTOMATICOS = 1;
    const ESPERA_REINTENTO_MS = 4000;

    const TEXTO_ESCRIBIENDO = typingIndicator
        ? typingIndicator.textContent.trim()
        : "";

    function esperar(ms) {
        return new Promise(function (resolver) {
            setTimeout(resolver, ms);
        });
    }

    // Hace UN intento. Retorna { ok, respuesta, reintentable }.
    async function consultarSonia(texto) {

        try {

            const response = await fetch(CHAT_ENDPOINT, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": CSRF_TOKEN,
                },
                body: JSON.stringify({
                    mensaje: texto,
                    historial: historial.slice(-MAX_HISTORIAL)
                }),
            });

            let data;

            try {
                data = await response.json();
            } catch (error) {
                // Respuesta que no es JSON (por ejemplo, el servidor se
                // demoró demasiado): vale la pena reintentar.
                return {
                    ok: false,
                    respuesta: "No se pudo conectar con el asistente. " +
                        "Intenta nuevamente en unos segundos.",
                    reintentable: true
                };
            }

            if (!response.ok || data.es_error || !data.respuesta) {

                console.error("Error de Sonia:", response.status, data);

                return {
                    ok: false,
                    respuesta: data.respuesta || data.error ||
                        "No pude generar una respuesta en este momento. " +
                        "Intenta nuevamente.",
                    reintentable: Boolean(data.reintentable)
                };
            }

            return { ok: true, respuesta: data.respuesta };

        } catch (error) {

            // Sin conexión o la petición no llegó al servidor
            console.error("Error al comunicarse con Sonia:", error);

            return {
                ok: false,
                respuesta: "No se pudo conectar con el asistente. " +
                    "Intenta nuevamente en unos segundos.",
                reintentable: true
            };
        }
    }

    // Pide la respuesta, reintentando solo si el error fue temporal,
    // y muestra el resultado en el chat.
    async function responderMensaje(texto) {

        mostrarEscribiendo();
        bloquearChat(true);

        let resultado = await consultarSonia(texto);

        for (
            let intento = 1;
            !resultado.ok && resultado.reintentable &&
            intento <= REINTENTOS_AUTOMATICOS;
            intento++
        ) {
            if (typingIndicator) {
                typingIndicator.textContent =
                    "Sonia está tardando un poco más de lo normal…";
            }

            await esperar(ESPERA_REINTENTO_MS);
            resultado = await consultarSonia(texto);
        }

        if (typingIndicator) {
            typingIndicator.textContent = TEXTO_ESCRIBIENDO;
        }

        ocultarEscribiendo();
        bloquearChat(false);

        if (resultado.ok) {

            agregarMensaje(resultado.respuesta, "sonia");

            // Solo las preguntas que Sonia respondió de verdad
            // pasan a formar parte de la conversación.
            historial.push(
                { rol: "usuario", texto: texto },
                { rol: "sonia", texto: resultado.respuesta }
            );

        } else {

            mostrarErrorConReintento(resultado.respuesta, texto);
        }

        input.focus();
    }

    // Mensaje de error con un botón para volver a preguntar lo mismo
    // sin tener que escribirlo de nuevo.
    function mostrarErrorConReintento(textoError, textoPregunta) {

        const mensaje = agregarMensaje(textoError, "sonia");

        if (!mensaje) {
            return;
        }

        const boton = document.createElement("button");
        boton.type = "button";
        boton.className = "btn-reintentar-sonia";
        boton.innerHTML = '<i class="bi bi-arrow-clockwise"></i> Reintentar';

        boton.addEventListener("click", function () {
            mensaje.remove();
            responderMensaje(textoPregunta);
        });

        mensaje.appendChild(boton);
        messages.scrollTop = messages.scrollHeight;
    }

    // =========================
    // ENVÍO DE MENSAJES
    // =========================

    if (form && input) {

        form.addEventListener("submit", function (e) {

            e.preventDefault();

            const texto = input.value.trim();

            // No enviar mensajes vacíos
            if (!texto) {
                mostrarAvisoVacio();
                return;
            }

            ocultarAvisoVacio();

            // Mostrar mensaje del usuario y limpiar el campo
            agregarMensaje(texto, "usuario");
            input.value = "";

            responderMensaje(texto);
        });

    }

});

