/* ===================================================
   ANIMACIONES DE DISEÑO & CONTROL DE MODAL Y CARGA
   Red Mamaria Preventiva
   =================================================== */
document.addEventListener("DOMContentLoaded", function () {

    /* ---- 1. Control de Selección y Carga de Imagen ---- */
    const dropzone = document.getElementById('dropzone');
    const input = document.getElementById('imagenInput');
    const previews = document.getElementById('previews');
    const avisoMaximo = document.getElementById('avisoMaximo');
    const submitBtn = document.getElementById('submitBtn');
    const MAXIMO_IMAGENES = dropzone ? Number(dropzone.dataset.maximo || 4) : 4;

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

    // Muestra una miniatura de cada imagen elegida (máximo MAXIMO_IMAGENES)
    function mostrarPreview() {
        let archivos = Array.from(input.files);
        if (!archivos.length) return;

        avisoMaximo.hidden = archivos.length <= MAXIMO_IMAGENES;
        if (archivos.length > MAXIMO_IMAGENES) {
            avisoMaximo.textContent = 'Puedes subir como máximo ' + MAXIMO_IMAGENES +
                ' imágenes. Usaremos solo las primeras ' + MAXIMO_IMAGENES + '.';
            archivos = archivos.slice(0, MAXIMO_IMAGENES);
            const transferencia = new DataTransfer();
            archivos.forEach(function (a) { transferencia.items.add(a); });
            input.files = transferencia.files;
        }

        previews.querySelectorAll('img').forEach(function (img) { URL.revokeObjectURL(img.src); });
        previews.innerHTML = '';
        archivos.forEach(function (archivo, i) {
            const img = document.createElement('img');
            img.src = URL.createObjectURL(archivo);
            img.alt = 'Imagen ' + (i + 1);
            previews.appendChild(img);
        });

        document.getElementById('dropzoneText').textContent = archivos.length === 1
            ? '1 imagen elegida (haz clic para cambiarla)'
            : archivos.length + ' imágenes elegidas (haz clic para cambiarlas)';
        document.getElementById('textoBotonAnalizar').textContent =
            archivos.length === 1 ? 'Analizar Imagen' : 'Analizar ' + archivos.length + ' Imágenes';

        if (submitBtn) {
            submitBtn.disabled = false;
        }
    }

    /* ---- 1b. Enviar las imágenes a analizar ----
       Vercel no acepta envíos de más de ~4,5 MB EN TOTAL. Si las imágenes
       pesan más que eso, se achican en el navegador antes de enviarlas
       (cada una se reduce hasta caber en su parte del límite; siempre
       queda mucho más grande que los 512x320 que usa el modelo). */
    const formAnalisis = document.getElementById('uploadForm');
    const LIMITE_TOTAL = 4 * 1024 * 1024;
    const LADO_MAXIMO = 2048;
    const LADO_MINIMO = 900;

    function canvasABlob(canvas, tipo, calidad) {
        return new Promise(function (resolver) {
            canvas.toBlob(resolver, tipo, calidad);
        });
    }

    async function reducirImagen(archivo, limite, numero) {
        const bitmap = await createImageBitmap(archivo);
        let lado = LADO_MAXIMO;
        let blob, nombre;

        // Se prueba PNG y luego JPEG; si aún pesa mucho, se achica de a poco
        while (true) {
            const escala = Math.min(1, lado / Math.max(bitmap.width, bitmap.height));
            const canvas = document.createElement('canvas');
            canvas.width = Math.round(bitmap.width * escala);
            canvas.height = Math.round(bitmap.height * escala);

            const ctx = canvas.getContext('2d');
            ctx.imageSmoothingQuality = 'high';
            ctx.drawImage(bitmap, 0, 0, canvas.width, canvas.height);

            blob = await canvasABlob(canvas, 'image/png');
            nombre = 'mamografia_' + numero + '.png';
            if (blob.size > limite) {
                blob = await canvasABlob(canvas, 'image/jpeg', 0.9);
                nombre = 'mamografia_' + numero + '.jpg';
            }
            if (blob.size <= limite || lado <= LADO_MINIMO) break;
            lado = Math.max(LADO_MINIMO, Math.round(lado * 0.8));
        }

        return new File([blob], nombre, { type: blob.type });
    }

    if (formAnalisis && input && submitBtn) {
        formAnalisis.addEventListener('submit', async function (e) {

            const archivos = Array.from(input.files);

            if (!archivos.length) {
                return;
            }

            submitBtn.disabled = true;
            submitBtn.innerHTML =
                '<span class="spinner-border spinner-border-sm me-2"></span>' +
                (archivos.length === 1 ? 'Analizando imagen…' : 'Analizando ' + archivos.length + ' imágenes…');

            const total = archivos.reduce(function (suma, a) { return suma + a.size; }, 0);
            if (total <= LIMITE_TOTAL) {
                return;   // se envían tal cual
            }

            e.preventDefault();

            try {
                const limitePorImagen = LIMITE_TOTAL / archivos.length;
                const transferencia = new DataTransfer();
                for (let i = 0; i < archivos.length; i++) {
                    const archivo = archivos[i];
                    transferencia.items.add(
                        archivo.size <= limitePorImagen ? archivo : await reducirImagen(archivo, limitePorImagen, i + 1)
                    );
                }
                input.files = transferencia.files;
            } catch (error) {
                console.error('No se pudieron reducir las imágenes:', error);
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