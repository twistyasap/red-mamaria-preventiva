/* ===================================================
   ANIMACIONES DE DISEÑO — Red Mamaria Preventiva
   Solo efectos visuales: no altera formularios, fetch
   ni la lógica de ninguna vista.
   =================================================== */
document.addEventListener("DOMContentLoaded", function () {

    /* ---- 1. Efecto "ripple" al hacer clic en botones ---- */
    document.querySelectorAll(".btn").forEach(function (btn) {
        btn.addEventListener("click", function (e) {
            const rect = btn.getBoundingClientRect();
            const ripple = document.createElement("span");
            const size = Math.max(rect.width, rect.height);
            ripple.classList.add("ripple");
            ripple.style.width = ripple.style.height = size + "px";
            ripple.style.left = (e.clientX - rect.left - size / 2) + "px";
            ripple.style.top = (e.clientY - rect.top - size / 2) + "px";
            btn.appendChild(ripple);
            setTimeout(function () { ripple.remove(); }, 600);
        });
    });

    /* ---- 2. Revelado progresivo al hacer scroll ---- */
    const revelables = document.querySelectorAll(
        ".card, .card-session, .reveal-on-scroll"
    );
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

    /* ---- 3. Transición suave entre páginas ----
       Solo intercepta enlaces internos normales (misma pestaña,
       sin target=_blank, sin # ni mailto/tel), para no afectar
       formularios, botones de submit ni enlaces externos. */
    document.querySelectorAll("a[href]").forEach(function (link) {
        const href = link.getAttribute("href");
        if (
            !href ||
            href.startsWith("#") ||
            href.startsWith("mailto:") ||
            href.startsWith("tel:") ||
            link.target === "_blank" ||
            link.hasAttribute("download")
        ) {
            return;
        }

        link.addEventListener("click", function (e) {
            e.preventDefault();
            document.body.classList.add("page-leaving");
            setTimeout(function () {
                window.location.href = href;
            }, 220);
        });
    });

    /* ---- 4. Arreglo del botón "Atrás" (bfcache) ----
       Cuando el navegador restaura una página desde su caché
       (al volver atrás), la clase "page-leaving" podía quedar
       pegada y dejaba la página invisible hasta un segundo clic.
       Esto la limpia apenas la página vuelve a mostrarse. */
    window.addEventListener("pageshow", function () {
        document.body.classList.remove("page-leaving");
    });
});