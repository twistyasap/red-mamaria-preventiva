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

    /* ---- 1b. Enviar la imagen a analizar ----
       Vercel no acepta envíos de más de ~4,5 MB. Si la imagen pesa más
       de 4 MB, se achica en el navegador (máx. 2048 px por lado, mucho
       más que los 512x320 que usa el modelo) antes de enviarla. */
    const formAnalisis = document.getElementById('uploadForm');
    const LIMITE_BYTES = 4 * 1024 * 1024;
    const LADO_MAXIMO = 2048;

    function canvasABlob(canvas, tipo, calidad) {
        return new Promise(function (resolver) {
            canvas.toBlob(resolver, tipo, calidad);
        });
    }

    async function reducirImagen(archivo) {
        const bitmap = await createImageBitmap(archivo);
        const escala = Math.min(1, LADO_MAXIMO / Math.max(bitmap.width, bitmap.height));

        const canvas = document.createElement('canvas');
        canvas.width = Math.round(bitmap.width * escala);
        canvas.height = Math.round(bitmap.height * escala);

        const ctx = canvas.getContext('2d');
        ctx.imageSmoothingQuality = 'high';
        ctx.drawImage(bitmap, 0, 0, canvas.width, canvas.height);

        let blob = await canvasABlob(canvas, 'image/png');
        let nombre = 'mamografia.png';

        if (blob.size > LIMITE_BYTES) {
            blob = await canvasABlob(canvas, 'image/jpeg', 0.92);
            nombre = 'mamografia.jpg';
        }

        return new File([blob], nombre, { type: blob.type });
    }

    if (formAnalisis && input && submitBtn) {
        formAnalisis.addEventListener('submit', async function (e) {

            const archivo = input.files[0];

            if (!archivo) {
                return;
            }

            submitBtn.disabled = true;
            submitBtn.innerHTML =
                '<span class="spinner-border spinner-border-sm me-2"></span>' +
                'Analizando imagen…';

            if (archivo.size <= LIMITE_BYTES) {
                return;   // se envía tal cual
            }

            e.preventDefault();

            try {
                const reducido = await reducirImagen(archivo);
                const transferencia = new DataTransfer();
                transferencia.items.add(reducido);
                input.files = transferencia.files;
            } catch (error) {
                console.error('No se pudo reducir la imagen:', error);
            }

            formAnalisis.submit();
        });
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