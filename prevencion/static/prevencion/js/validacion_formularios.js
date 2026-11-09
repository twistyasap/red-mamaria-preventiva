/* ===================================================
   VALIDACIÓN DE FORMULARIOS
   Muestra mensajes propios debajo de cada campo en vez
   del aviso genérico del navegador.

   Uso: agregar data-validar al <form> y, a cada campo
   obligatorio, required y data-nombre="Nombre visible".
   =================================================== */
document.addEventListener("DOMContentLoaded", function () {

    const formularios = document.querySelectorAll("form[data-validar]");

    formularios.forEach(function (form) {

        // Desactiva el aviso del navegador ("Completa este campo")
        form.setAttribute("novalidate", "");

        const campos = form.querySelectorAll("[required]");

        form.addEventListener("submit", function (e) {

            let primerCampoConError = null;

            campos.forEach(function (campo) {

                const error = validarCampo(campo);

                if (error) {
                    mostrarError(campo, error);
                    primerCampoConError = primerCampoConError || campo;
                } else {
                    limpiarError(campo);
                }
            });

            if (primerCampoConError) {
                e.preventDefault();
                primerCampoConError.focus();
            }
        });

        // El mensaje desaparece en cuanto la persona empieza a escribir
        campos.forEach(function (campo) {
            campo.addEventListener("input", function () {
                limpiarError(campo);
            });
        });
    });

    function validarCampo(campo) {

        const valor = campo.value.trim();
        const nombre = campo.dataset.nombre || "obligatorio";

        if (!valor) {
            return "Falta llenar el campo " + nombre + ".";
        }

        if (campo.type === "email" && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(valor)) {
            return "El correo no tiene un formato válido (ej: nombre@correo.com).";
        }

        if (campo.dataset.requisitos) {
            const pendientes = REGLAS_CLAVE.filter(function (r) { return !r.cumple(campo.value); });
            if (pendientes.length) {
                return "La contraseña no cumple: " +
                    pendientes.map(function (r) { return r.texto; }).join(", ") + ".";
            }
        }

        return null;
    }

    /* ---- Requisitos de contraseña (iguales a prevencion/validators.py) ---- */
    const REGLAS_CLAVE = [
        { id: "largo",     texto: "mínimo 8 caracteres",
          cumple: function (v) { return v.length >= 8; } },
        { id: "mayuscula", texto: "la primera letra en mayúscula",
          cumple: function (v) { return v.length > 0 && v[0] !== v[0].toLowerCase() && v[0] === v[0].toUpperCase(); } },
        { id: "numero",    texto: "al menos un número",
          cumple: function (v) { return /\d/.test(v); } }
    ];

    document.querySelectorAll("[data-requisitos]").forEach(function (campo) {
        const lista = document.getElementById(campo.dataset.requisitos);
        if (!lista) return;

        function actualizar() {
            REGLAS_CLAVE.forEach(function (regla) {
                const item = lista.querySelector('[data-regla="' + regla.id + '"]');
                if (!item) return;
                const ok = regla.cumple(campo.value);
                item.classList.toggle("cumple", ok);
                const icono = item.querySelector("i");
                icono.className = ok ? "bi bi-check-circle-fill" : "bi bi-circle";
            });
        }

        campo.addEventListener("input", actualizar);
        actualizar();
    });

    // El mensaje va debajo del campo, o debajo del grupo con ícono si lo tiene
    function contenedorDe(campo) {
        return campo.closest(".input-group") || campo;
    }

    function mostrarError(campo, texto) {

        campo.classList.add("is-invalid");

        const contenedor = contenedorDe(campo);
        let mensaje = contenedor.nextElementSibling;

        if (!mensaje || !mensaje.classList.contains("campo-error")) {
            mensaje = document.createElement("div");
            mensaje.className = "campo-error";
            contenedor.insertAdjacentElement("afterend", mensaje);
        }

        mensaje.innerHTML = '<i class="bi bi-exclamation-circle-fill"></i> ';
        mensaje.append(texto);
    }

    function limpiarError(campo) {

        campo.classList.remove("is-invalid");

        const mensaje = contenedorDe(campo).nextElementSibling;

        if (mensaje && mensaje.classList.contains("campo-error")) {
            mensaje.remove();
        }
    }
});
