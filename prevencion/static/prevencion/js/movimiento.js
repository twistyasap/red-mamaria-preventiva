/* ===================================================
   MOVIMIENTO GLOBAL — Red Mamaria Preventiva
   - Apariciones al deslizar (con escalonado)
   - Transición con cortina al cambiar de página
   - Barra de progreso, parallax del fondo, volver arriba
   - Onda al pulsar botones
   Todo pensado para no trabar: un solo IntersectionObserver,
   scroll pasivo agrupado con requestAnimationFrame y pausa
   cuando la pestaña no está visible.
   =================================================== */
(function () {
    'use strict';

    var html = document.documentElement;
    var reducir = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    /* ---- Modo liviano en equipos con pocos recursos ---- */
    var con = navigator.connection || {};
    if ((navigator.hardwareConcurrency && navigator.hardwareConcurrency <= 2) ||
        (navigator.deviceMemory && navigator.deviceMemory <= 2) ||
        con.saveData) {
        html.classList.add('rm-liviano');
    }

    /* ---- Pausar el fondo si la pestaña está oculta ---- */
    function revisarVisibilidad() {
        html.classList.toggle('rm-pausa', document.hidden);
    }
    document.addEventListener('visibilitychange', revisarVisibilidad);
    revisarVisibilidad();

    /* ---- Volver con el botón "atrás" (bfcache) ---- */
    window.addEventListener('pageshow', function (e) {
        if (e.persisted) document.body.classList.remove('page-leaving');
    });

    function iniciar() {
        iniciarTransiciones();
        if (reducir) return;
        // Se espera un tick para que animaciones.js / landing.js
        // marquen primero sus propios elementos.
        setTimeout(iniciarApariciones, 0);
        iniciarScroll();
        iniciarOndas();
        iniciarBrillo();
    }

    /* =========== 1. Transición entre páginas =========== */
    function iniciarTransiciones() {
        document.addEventListener('click', function (e) {
            if (e.defaultPrevented || e.button !== 0 ||
                e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;

            var a = e.target.closest ? e.target.closest('a[href]') : null;
            if (!a) return;
            if (a.target && a.target !== '_self') return;
            if (a.hasAttribute('download') || a.hasAttribute('data-bs-toggle') ||
                a.hasAttribute('data-no-transicion')) return;

            var href = a.getAttribute('href');
            if (!href || href.charAt(0) === '#' || /^(mailto:|tel:|javascript:)/i.test(href)) return;

            var destino;
            try { destino = new URL(a.href, location.href); } catch (err) { return; }
            if (destino.origin !== location.origin) return;
            // Mismo documento, solo cambia el ancla
            if (destino.pathname === location.pathname && destino.search === location.search && destino.hash) return;

            if (reducir) return;
            e.preventDefault();
            document.body.classList.add('page-leaving');
            setTimeout(function () { location.href = destino.href; }, 260);
        });
    }

    /* =========== 2. Apariciones al deslizar =========== */
    var OBJETIVOS = [
        '.row > [class*="col"]', '.card', '.card-session',
        'h1', 'h2', 'h3', 'h4', '.lead', 'p',
        'img', 'hr', 'table', 'blockquote', '.alert',
        '.list-group-item', '.accordion-item', 'li', '.btn-lg', 'iframe'
    ].join(',');

    var EXCLUIR = [
        '#rm-fondo', '.rm-transicion', 'nav', '.navbar', 'header.sticky-top',
        '.modal', '#modalOpcional', '[class*="chat-widget"]', '[class*="chat-"]',
        '.leaflet-container', '.dropdown-menu', '.offcanvas', '.toast',
        '.aparece', '.reveal-on-scroll', '[data-no-anim]', 'form', 'button',
        '.rm-rev'
    ].join(',');

    function variantePara(el, indice) {
        var tag = el.tagName;
        if (tag === 'IMG' || tag === 'IFRAME' || tag === 'TABLE') return 'rm-zoom';
        if (tag === 'LI' || el.classList.contains('list-group-item')) return 'rm-izquierda';
        if (el.matches('.card, .card-session')) return 'rm-giro';
        if (el.matches('.row > [class*="col"]')) {
            var hermanos = el.parentElement.children.length;
            if (hermanos === 2) return indice === 0 ? 'rm-izquierda' : 'rm-derecha';
            return indice % 3 === 1 ? 'rm-giro' : 'rm-arriba';
        }
        return 'rm-arriba';
    }

    function iniciarApariciones() {
        if (!('IntersectionObserver' in window)) return;

        var candidatos = document.querySelectorAll(OBJETIVOS);
        var elegidos = [];

        for (var i = 0; i < candidatos.length; i++) {
            var el = candidatos[i];
            if (el.closest(EXCLUIR)) continue;            // ya animado o excluido
            if (getComputedStyle(el).position === 'fixed') continue;
            var indice = Array.prototype.indexOf.call(el.parentElement.children, el);
            el.classList.add('rm-rev', variantePara(el, indice));
            elegidos.push(el);
        }

        var observador = new IntersectionObserver(function (entradas) {
            // Escalona los que aparecen juntos dentro del mismo padre
            var porPadre = new Map();
            entradas.forEach(function (entrada) {
                if (!entrada.isIntersecting) return;
                var padre = entrada.target.parentElement;
                var n = porPadre.get(padre) || 0;
                porPadre.set(padre, n + 1);
                revelar(entrada.target, Math.min(n * 90, 450));
                observador.unobserve(entrada.target);
            });
        }, { threshold: 0.08, rootMargin: '0px 0px -6% 0px' });

        elegidos.forEach(function (el) { observador.observe(el); });
    }

    function revelar(el, retraso) {
        if (retraso) el.style.transitionDelay = retraso + 'ms';
        // doble rAF: asegura que el estado inicial se pintó antes
        requestAnimationFrame(function () {
            requestAnimationFrame(function () { el.classList.add('rm-visible'); });
        });
        // Al terminar se limpian las clases para no interferir
        // con los hover propios (p. ej. tarjetas que suben).
        setTimeout(function () {
            el.classList.remove('rm-rev', 'rm-visible', 'rm-arriba', 'rm-izquierda',
                                'rm-derecha', 'rm-zoom', 'rm-giro');
            el.style.transitionDelay = '';
        }, 950 + retraso);
    }

    /* =========== 3. Scroll: progreso, parallax, volver arriba =========== */
    function iniciarScroll() {
        var barra = document.createElement('div');
        barra.className = 'rm-progreso';
        barra.setAttribute('aria-hidden', 'true');
        document.body.appendChild(barra);

        var boton = document.createElement('button');
        boton.type = 'button';
        boton.className = 'rm-arriba-btn';
        boton.setAttribute('aria-label', 'Volver arriba');
        boton.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 19V5M5 12l7-7 7 7"/></svg>';
        boton.addEventListener('click', function () { window.scrollTo({ top: 0, behavior: 'smooth' }); });
        document.body.appendChild(boton);

        var lazos = document.querySelector('#rm-fondo .rm-lazos');
        var pendiente = false;

        function actualizar() {
            pendiente = false;
            var y = window.pageYOffset || html.scrollTop;
            var max = html.scrollHeight - window.innerHeight;
            barra.style.transform = 'scaleX(' + (max > 0 ? Math.min(y / max, 1) : 0) + ')';
            boton.classList.toggle('rm-mostrar', y > 500);
            if (lazos) lazos.style.transform = 'translate3d(0,' + (-y * 0.06).toFixed(1) + 'px,0)';
        }

        window.addEventListener('scroll', function () {
            if (!pendiente) { pendiente = true; requestAnimationFrame(actualizar); }
        }, { passive: true });
        window.addEventListener('resize', actualizar, { passive: true });
        actualizar();
    }

    /* =========== 4. Onda al pulsar botones =========== */
    function iniciarOndas() {
        document.addEventListener('pointerdown', function (e) {
            var btn = e.target.closest && e.target.closest('.btn, .rm-arriba-btn');
            if (!btn || btn.disabled) return;
            btn.classList.add('rm-onda-host');
            var r = btn.getBoundingClientRect();
            var lado = Math.max(r.width, r.height) * 2.2;
            var onda = document.createElement('span');
            onda.className = 'rm-onda';
            onda.style.width = onda.style.height = lado + 'px';
            onda.style.left = (e.clientX - r.left - lado / 2) + 'px';
            onda.style.top = (e.clientY - r.top - lado / 2) + 'px';
            btn.appendChild(onda);
            onda.addEventListener('animationend', function () { onda.remove(); });
        }, { passive: true });
    }

    /* =========== 5. Brillo en el título principal =========== */
    function iniciarBrillo() {
        var h1 = document.querySelector('h1');
        if (!h1 || h1.children.length) return;          // solo texto plano
        var cs = getComputedStyle(h1);
        if ((cs.webkitBackgroundClip || cs.backgroundClip) === 'text') return;
        h1.classList.add('rm-brillo');
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', iniciar);
    } else {
        iniciar();
    }
})();
