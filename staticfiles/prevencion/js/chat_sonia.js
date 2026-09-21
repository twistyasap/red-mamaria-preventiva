document.addEventListener("DOMContentLoaded", function () {
    const toggleBtn = document.getElementById("toggleChatBtn");
    const closeBtn = document.getElementById("closeChatBtn");
    const chatBox = document.getElementById("chatWidgetBox");

    const form = document.getElementById("chatForm");
    const input = document.getElementById("chatInput");
    const messages = document.getElementById("chatMessages");
    const typingIndicator = document.getElementById("typingIndicator");

    /* Apertura / Cierre de la ventana flotante */
    if (toggleBtn && chatBox) {
        toggleBtn.addEventListener("click", function () {
            chatBox.classList.toggle("is-open");
            if (chatBox.classList.contains("is-open")) {
                input.focus();
            }
        });
    }

    if (closeBtn && chatBox) {
        closeBtn.addEventListener("click", function () {
            chatBox.classList.remove("is-open");
        });
    }

    function agregarMensaje(texto, tipo) {
        const div = document.createElement("div");
        div.className = "msg " + (tipo === "usuario" ? "msg-usuario" : "msg-sonia");
        div.textContent = texto;
        messages.appendChild(div);
        messages.scrollTop = messages.scrollHeight;
    }

    if (form) {
        form.addEventListener("submit", function (e) {
            e.preventDefault();
            const texto = input.value.trim();
            if (!texto) return;

            agregarMensaje(texto, "usuario");
            input.value = "";
            typingIndicator.style.display = "block";

            fetch(CHAT_ENDPOINT, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": CSRF_TOKEN,
                },
                body: JSON.stringify({ mensaje: texto }),
            })
                .then((res) => res.json())
                .then((data) => {
                    typingIndicator.style.display = "none";
                    if (data.respuesta) {
                        agregarMensaje(data.respuesta, "sonia");
                    } else {
                        agregarMensaje("Ocurrió un error al procesar tu mensaje. Intenta nuevamente.", "sonia");
                    }
                })
                .catch(() => {
                    typingIndicator.style.display = "none";
                    agregarMensaje("No se pudo conectar con el asistente. Revisa tu conexión e intenta de nuevo.", "sonia");
                });
        });
    }
});