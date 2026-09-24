/* ===================================================
   ANIMACIONES DE DISEÑO & CONTROL DE MODAL Y CARGA
   Red Mamaria Preventiva
   =================================================== */
document.addEventListener("DOMContentLoaded", function () {

    /* ---- 1. Control de Selección y Carga de Imagen ---- */
    const dropzone = document.getElementById('dropzone');
    const input = document.getElementById('imagenInput');
    const preview = document.getElementById('previewImg');
    const submitBtn = document.getElementById('submitBtn');

    if (dropzone && input) {
        dropzone.addEventListener('click', () => input.click());

        dropzone.addEventListener('dragover', (e) => {
            e.preventDefault();
            dropzone.classList.add('dragover');
        });

        dropzone.addEventListener('dragleave', () => dropzone.classList.remove('dragover'));

        dropzone.addEventListener('drop', (e) => {
            e.preventDefault();
            dropzone.classList.remove('dragover');
            if (e.dataTransfer.files.length) {
                input.files = e.dataTransfer.files;
                mostrarPreview();
            }
        });

        input.addEventListener('change', mostrarPreview);
    }

    function mostrarPreview() {
        const file = input.files[0];
        if (!file) return;
        const reader = new FileReader();
        reader.onload = (e) => {
            if (preview) {
                preview.src = e.target.result;
                preview.style.display = 'inline-block';
            }
        };
        reader.readAsDataURL(file);
        if (submitBtn) {
            submitBtn.disabled = false;
        }
    }

    /* ---- 2. Mostrar Modal al Cargar ---- */
    const modal = document.getElementById('modalOpcional');
    if (modal) {
        modal.style.display = 'flex';
        modal.style.opacity = '1';
    }

    /* ---- 3. Revelado progresivo al hacer scroll ---- */
    const revelables = document.querySelectorAll(".card, .card-session, .reveal-on-scroll");
    revelables.forEach(function (el) { el.classList.add("reveal-on-scroll"); });

    if ("IntersectionObserver" in window) {
        const observer = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (entry.isIntersecting) {
                    entry.target.classList.add("is-visible");
                    observer.unobserve(entry.target);
                }
            });
        }, { threshold: 0.12 });

        revelables.forEach(function (el) { observer.observe(el); });
    } else {
        revelables.forEach(function (el) { el.classList.add("is-visible"); });
    }

    /* ---- 4. Navegación segura solo para la flecha de volver ---- */
    document.querySelectorAll(".nav-link-custom").forEach(function (link) {
        link.addEventListener("click", function (e) {
            const href = link.getAttribute("href");
            if (href && href !== "#") {
                e.preventDefault();
                document.body.classList.add("page-leaving");
                setTimeout(function () {
                    window.location.href = href;
                }, 220);
            }
        });
    });

    window.addEventListener("pageshow", function () {
        document.body.classList.remove("page-leaving");
    });
});

/* ---- Funciones Globales para Cerrar Modal ---- */
function cerrarModal() {
    const modal = document.getElementById('modalOpcional');
    if (modal) {
        modal.style.opacity = '0';
        setTimeout(() => {
            modal.style.setProperty('display', 'none', 'important');
        }, 200);
    }
}

// Cerrar si hace clic fuera del recuadro blanco
window.addEventListener('click', function(event) {
    const modal = document.getElementById('modalOpcional');
    if (event.target === modal) {
        cerrarModal();
    }
});