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
    // ENVÍO DE MENSAJES
    // =========================

    if (form && input) {

        form.addEventListener("submit", async function (e) {

            e.preventDefault();

            const texto = input.value.trim();

            // No enviar mensajes vacíos
            if (!texto) {
                return;
            }

            // Mostrar mensaje del usuario
            agregarMensaje(texto, "usuario");

            // Limpiar input
            input.value = "";

            // Mostrar indicador de escritura
            mostrarEscribiendo();

            // Evitar mensajes duplicados mientras responde Gemini
            bloquearChat(true);

            try {

                const response = await fetch(CHAT_ENDPOINT, {

                    method: "POST",

                    headers: {
                        "Content-Type": "application/json",
                        "X-CSRFToken": CSRF_TOKEN,
                    },

                    body: JSON.stringify({
                        mensaje: texto
                    }),

                });

                let data;

                try {
                    data = await response.json();
                } catch (error) {

                    throw new Error(
                        "El servidor devolvió una respuesta inválida."
                    );
                }

                ocultarEscribiendo();

                // Si Django respondió con error HTTP
                if (!response.ok) {

                    console.error(
                        "Error HTTP:",
                        response.status,
                        data
                    );

                    agregarMensaje(
                        data.respuesta ||
                        data.error ||
                        "Ocurrió un error al procesar tu mensaje.",
                        "sonia"
                    );

                    return;
                }

                // Respuesta correcta del chatbot
                if (data.respuesta) {

                    agregarMensaje(
                        data.respuesta,
                        "sonia"
                    );

                } else {

                    agregarMensaje(
                        "No pude generar una respuesta en este momento. Intenta nuevamente.",
                        "sonia"
                    );
                }

            } catch (error) {

                ocultarEscribiendo();

                console.error(
                    "Error al comunicarse con Sonia:",
                    error
                );

                agregarMensaje(
                    "No se pudo conectar con el asistente. Intenta nuevamente en unos segundos.",
                    "sonia"
                );

            } finally {

                // Reactivar input
                bloquearChat(false);

                // Volver a colocar cursor
                input.focus();
            }

        });

    }

});

