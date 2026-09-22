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

        div.textContent = texto;

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

