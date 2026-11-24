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
    // (Markdown básico que escribe la IA)
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

    // Celdas de una fila de tabla ("| a | b |"), o null si no es una fila
    function celdasTabla(linea) {

        if (!/^\|.*\|$/.test(linea)) {
            return null;
        }

        return linea.slice(1, -1).split("|").map(function (celda) {
            return celda.trim();
        });
    }

    // Fila "|---|:---:|" que separa el encabezado del resto de la tabla
    function esSeparadorTabla(celdas) {
        return Boolean(celdas) && celdas.every(function (celda) {
            return /^:?-{2,}:?$/.test(celda);
        });
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

        function abrirLista(tipoLista) {
            if (listaAbierta !== tipoLista) {
                cerrarLista();
                html.push("<" + tipoLista + ">");
                listaAbierta = tipoLista;
            }
        }

        lineas.forEach(function (linea, i) {

            const limpia = linea.trim();
            const vineta = limpia.match(/^[*\-•]\s+(.*)$/);
            const numero = limpia.match(/^\d+[.)]\s+(.*)$/);
            const titulo = limpia.match(/^#{1,6}\s+(.*)$/);
            const fila = celdasTabla(limpia);

            // Línea separadora (---): no se muestra
            if (/^(-{3,}|\*{3,}|_{3,})$/.test(limpia)) {
                cerrarLista();
                return;
            }

            // Las tablas no caben bien en la burbuja del chat: cada fila se
            // muestra como un punto de lista ("primera celda: el resto") y
            // se omite el encabezado.
            if (fila) {

                const siguiente = celdasTabla((lineas[i + 1] || "").trim());

                if (esSeparadorTabla(fila) || esSeparadorTabla(siguiente)) {
                    return;
                }

                const resto = fila.slice(1).filter(Boolean);

                abrirLista("ul");
                html.push(
                    "<li><strong>" +
                    formatoEnLinea(fila[0].replace(/\*\*/g, "")) +
                    "</strong>" +
                    (resto.length ? ": " + resto.map(formatoEnLinea).join(" · ") : "") +
                    "</li>"
                );
                return;
            }

            if (vineta || numero) {

                abrirLista(vineta ? "ul" : "ol");

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
    // SONIA RESPONDE
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

    const ERROR_CONEXION =
        "No se pudo conectar con el asistente. " +
        "Intenta nuevamente en unos segundos.";

    // Hace UN intento y lee la respuesta a medida que el servidor la
    // envía (streaming): una línea JSON por evento.
    //   {"texto": "..."}               -> trozo de la respuesta
    //   {"fin": true, "respaldo": ...} -> terminó
    // Llama a alRecibirTexto(textoAcumulado) con cada trozo.
    // Retorna { ok, respuesta, respaldo, completa }.
    async function consultarSonia(texto, alRecibirTexto) {

        let respuesta = "";
        let fin = null;

        function procesarLinea(linea) {

            if (!linea.trim()) {
                return;
            }

            let evento;

            try {
                evento = JSON.parse(linea);
            } catch (error) {
                return;
            }

            if (evento.texto) {
                respuesta += evento.texto;
                alRecibirTexto(respuesta);
            }

            if (evento.fin) {
                fin = evento;
            }
        }

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

            const tipo = response.headers.get("Content-Type") || "";

            // Errores del servidor (JSON) o la sesión expiró (HTML)
            if (!response.ok || !tipo.includes("ndjson") || !response.body) {

                let data = {};

                try {
                    data = await response.json();
                } catch (error) {
                    // No es JSON
                }

                console.error("Error de Sonia:", response.status, data);

                return {
                    ok: false,
                    respuesta: data.respuesta || data.error || ERROR_CONEXION
                };
            }

            const lector = response.body.getReader();
            const decodificador = new TextDecoder();
            let pendiente = "";

            while (true) {

                const { value, done } = await lector.read();

                if (done) {
                    break;
                }

                pendiente += decodificador.decode(value, { stream: true });

                const lineas = pendiente.split("\n");
                pendiente = lineas.pop();
                lineas.forEach(procesarLinea);
            }

            procesarLinea(pendiente + decodificador.decode());

        } catch (error) {

            // Sin conexión, o se cortó a la mitad de la respuesta
            console.error("Error al comunicarse con Sonia:", error);
        }

        if (!respuesta) {
            return { ok: false, respuesta: ERROR_CONEXION };
        }

        return {
            ok: true,
            respuesta: respuesta,
            respaldo: Boolean(fin && fin.respaldo),
            completa: Boolean(fin && !fin.incompleta)
        };
    }

    // Pide la respuesta (un solo intento, para no gastar llamadas a
    // la IA) y la va mostrando en el chat mientras se escribe.
    async function responderMensaje(texto) {

        mostrarEscribiendo();
        bloquearChat(true);

        let burbuja = null;
        let ultimoTexto = "";
        let pintadoPendiente = false;

        // Repinta como máximo una vez por cuadro de pantalla, aunque
        // lleguen muchos trozos seguidos.
        function pintar() {
            pintadoPendiente = false;
            burbuja.innerHTML = formatearMarkdown(ultimoTexto);
            messages.scrollTop = messages.scrollHeight;
        }

        const resultado = await consultarSonia(texto, function (acumulado) {

            ultimoTexto = acumulado;

            if (!burbuja) {
                ocultarEscribiendo();
                burbuja = agregarMensaje("", "sonia");
            }

            if (burbuja && !pintadoPendiente) {
                pintadoPendiente = true;
                requestAnimationFrame(pintar);
            }
        });

        ocultarEscribiendo();
        bloquearChat(false);

        if (burbuja) {
            // Pintado final, por si quedó un trozo sin mostrar
            ultimoTexto = resultado.ok ? resultado.respuesta : ultimoTexto;
            pintar();
        }

        if (!resultado.ok) {

            if (burbuja) {
                burbuja.remove();
            }

            mostrarErrorConReintento(resultado.respuesta, texto);

        } else if (!resultado.completa) {

            // Se cortó a la mitad: se deja lo que llegó y se ofrece
            // volver a preguntar.
            agregarBotonReintento(burbuja, texto);

        } else if (!resultado.respaldo) {

            // Solo las respuestas de la IA pasan a formar parte de la
            // conversación (las de respaldo son información general).
            historial.push(
                { rol: "usuario", texto: texto },
                { rol: "sonia", texto: resultado.respuesta }
            );
        }

        input.focus();
    }

    // Botón para volver a preguntar lo mismo sin tener que
    // escribirlo de nuevo.
    function agregarBotonReintento(mensaje, textoPregunta) {

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

    function mostrarErrorConReintento(textoError, textoPregunta) {
        agregarBotonReintento(agregarMensaje(textoError, "sonia"), textoPregunta);
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

