/* ===================================================
   ANIMACIONES — Página de análisis de imagen
   Red Mamaria Preventiva

   No cambia la lógica de subida (está en animaciones.js):
   solo escucha los mismos eventos y agrega movimiento.
   =================================================== */
(function () {
    'use strict';

    var reducir = window.matchMedia &&
        window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    // El mismo lazo del fondo animado (_fondo_animado.html)
    var LAZO = '<svg viewBox="0 -4 100 146" aria-hidden="true" style="display:block;width:100%;height:auto">' +
        '<use href="#rm-lazo"/></svg>';

    function iniciar() {
        iniciarZona();
        iniciarPasos();
        iniciarCargando();
        iniciarResultado();
        iniciarError();
    }

    /* =========== 1. Zona para soltar + vista previa =========== */
    function iniciarZona() {
        var zona = document.getElementById('dropzone');
        var input = document.getElementById('imagenInput');
        var foto = document.getElementById('previewImg');
        var texto = document.getElementById('dropzoneText');
        var boton = document.getElementById('submitBtn');
        if (!zona || !input) return;

        function anillos() {
            if (reducir) return;
            for (var i = 0; i < 2; i++) {
                var a = document.createElement('span');
                a.className = 'an-anillo';
                zona.appendChild(a);
                a.addEventListener('animationend', function () { this.remove(); });
            }
        }

        function archivoElegido() {
            var archivo = input.files && input.files[0];
            if (!archivo) return;

            anillos();

            if (texto) {
                texto.classList.remove('an-listo');
                void texto.offsetWidth;            // reinicia la animación
                texto.textContent = '¡Listo! ' + archivo.name;
                texto.classList.add('an-listo');
            }

            // animaciones.js carga la foto; se anima cuando llega
            if (foto) {
                foto.classList.remove('an-aparece');
                foto.addEventListener('load', function alCargar() {
                    foto.removeEventListener('load', alCargar);
                    void foto.offsetWidth;
                    foto.classList.add('an-aparece');
                });
            }

            if (boton) boton.classList.add('an-pulso');
        }

        input.addEventListener('change', archivoElegido);
        // El "drop" asigna input.files sin disparar "change"
        zona.addEventListener('drop', function () { setTimeout(archivoElegido, 0); });
    }

    /* =========== 2. Pasos que se encienden en orden =========== */
    function iniciarPasos() {
        var pasos = document.querySelectorAll('.paso-analisis');
        if (!pasos.length || reducir) return;

        var actual = -1;
        var timer = null;

        function siguiente() {
            if (actual >= 0) pasos[actual].classList.remove('an-activo');
            actual = (actual + 1) % pasos.length;
            pasos[actual].classList.add('an-activo');
        }

        function arrancar() {
            if (timer) return;
            siguiente();
            timer = setInterval(siguiente, 1800);
        }
        function detener() {
            clearInterval(timer);
            timer = null;
        }

        // Solo se anima mientras la sección está a la vista
        if ('IntersectionObserver' in window) {
            new IntersectionObserver(function (entradas) {
                entradas[0].isIntersecting ? arrancar() : detener();
            }, { threshold: 0.3 }).observe(pasos[0].closest('.card-session') || pasos[0]);
        } else {
            arrancar();
        }

        // Al pasar el mouse, ese paso toma el protagonismo
        pasos.forEach(function (paso, i) {
            paso.addEventListener('mouseenter', function () {
                detener();
                pasos.forEach(function (p) { p.classList.remove('an-activo'); });
                actual = i;
                paso.classList.add('an-activo');
            });
            paso.addEventListener('mouseleave', function () {
                setTimeout(arrancar, 600);
            });
        });

        document.addEventListener('visibilitychange', function () {
            document.hidden ? detener() : arrancar();
        });
    }

    /* =========== 3. Pantalla "Analizando…" =========== */
    var MENSAJES = [
        'Preparando tu imagen…',
        'Recortando la mama y quitando etiquetas…',
        'La red neuronal está revisando la imagen…',
        'Buscando zonas que llamen la atención…',
        'Generando el mapa de calor…',
        'Ya casi está listo…'
    ];

    function redNeuronal() {
        // 3 capas: 4 - 5 - 2 neuronas
        var capas = [[20, [18, 44, 70, 96]], [120, [10, 32, 57, 82, 104]], [220, [40, 74]]];
        var lineas = '', circulos = '', retraso = 0;

        for (var c = 0; c < capas.length - 1; c++) {
            capas[c][1].forEach(function (y1) {
                capas[c + 1][1].forEach(function (y2) {
                    lineas += '<line x1="' + capas[c][0] + '" y1="' + y1 +
                              '" x2="' + capas[c + 1][0] + '" y2="' + y2 + '"/>';
                });
            });
        }
        capas.forEach(function (capa) {
            capa[1].forEach(function (y) {
                circulos += '<circle cx="' + capa[0] + '" cy="' + y + '" r="6" style="animation-delay:' +
                            (retraso += 0.12).toFixed(2) + 's"/>';
            });
        });

        return '<svg class="an-red" viewBox="0 0 240 114" aria-hidden="true">' + lineas + circulos + '</svg>';
    }

    function iniciarCargando() {
        var form = document.getElementById('uploadForm');
        var input = document.getElementById('imagenInput');
        var foto = document.getElementById('previewImg');
        if (!form || !input) return;

        var velo = null, timers = [];

        form.addEventListener('submit', function () {
            if (!input.files || !input.files[0] || velo) return;

            var src = foto && foto.src && foto.style.display !== 'none' ? foto.src : '';
            var puntos = '';
            [[30, 35], [62, 48], [44, 70], [70, 25], [38, 55]].forEach(function (p, i) {
                puntos += '<span class="an-punto" style="left:' + p[0] + '%;top:' + p[1] +
                          '%;animation-delay:' + (i * 0.45).toFixed(2) + 's"></span>';
            });

            velo = document.createElement('div');
            velo.className = 'an-cargando';
            velo.setAttribute('role', 'status');
            velo.setAttribute('aria-live', 'polite');
            velo.innerHTML =
                '<div class="an-cargando-tarjeta">' +
                    '<div class="an-escaner">' +
                        (src ? '<img src="' + src + '" alt="">'
                             : '<div class="an-escaner-sin-foto"><i class="bi bi-image"></i></div>') +
                        puntos +
                        '<span class="an-esquina e1"></span><span class="an-esquina e2"></span>' +
                        '<span class="an-esquina e3"></span><span class="an-esquina e4"></span>' +
                        '<div class="an-linea"></div>' +
                    '</div>' +
                    redNeuronal() +
                    '<p class="an-cargando-titulo">Analizando tu mamografía</p>' +
                    '<p class="an-mensaje">' + MENSAJES[0] + '</p>' +
                    '<div class="an-progreso"><span></span></div>' +
                    '<p class="an-cargando-pie"><i class="bi bi-shield-lock me-1"></i>Tu imagen no se guarda.</p>' +
                '</div>';
            document.body.appendChild(velo);

            var mensaje = velo.querySelector('.an-mensaje');
            var barra = velo.querySelector('.an-progreso span');
            var i = 0, avance = 0;

            timers.push(setInterval(function () {
                if (i >= MENSAJES.length - 1) return;
                i++;
                mensaje.textContent = MENSAJES[i];
                mensaje.classList.remove('an-cambia');
                void mensaje.offsetWidth;
                mensaje.classList.add('an-cambia');
            }, 1700));

            // Avanza rápido al principio y se frena cerca del 92 %
            timers.push(setInterval(function () {
                avance += (0.92 - avance) * 0.08;
                barra.style.transform = 'scaleX(' + avance.toFixed(3) + ')';
            }, 250));
        });

        // Si vuelve con el botón "atrás", quitar la pantalla
        window.addEventListener('pageshow', function (e) {
            if (e.persisted && velo) {
                timers.forEach(clearInterval);
                timers = [];
                velo.remove();
                velo = null;
            }
        });
    }

    /* =========== 4. Resultado =========== */
    function iniciarResultado() {
        var res = document.getElementById('resultado');
        if (!res) return;

        res.classList.add('an-resultado');

        // Llevar la vista al resultado con suavidad
        if (!reducir && res.getBoundingClientRect().top > 120) {
            setTimeout(function () { res.scrollIntoView({ behavior: 'smooth', block: 'start' }); }, 300);
        }

        // Contador 0 → índice, sincronizado con la barra
        var numero = res.querySelector('[data-contar]');
        if (numero) {
            var meta = parseInt(numero.getAttribute('data-contar'), 10) || 0;
            if (reducir) {
                numero.textContent = meta;
            } else {
                numero.textContent = '0';
                setTimeout(function () {
                    var inicio = null, dur = 1300;
                    function paso(t) {
                        if (!inicio) inicio = t;
                        var p = Math.min((t - inicio) / dur, 1);
                        var suave = 1 - Math.pow(1 - p, 3);
                        numero.textContent = Math.round(meta * suave);
                        if (p < 1) requestAnimationFrame(paso);
                        else numero.classList.add('an-fin');
                    }
                    requestAnimationFrame(paso);
                }, 1100);
            }
        }

        // Lazos que salen de la tarjeta, solo con resultado Verde
        var tarjeta = res.querySelector('.nivel-tarjeta.nivel-Verde');
        if (tarjeta && !reducir) {
            setTimeout(function () { lluviaDeLazos(tarjeta); }, 1300);
        }
    }

    function lluviaDeLazos(tarjeta) {
        var colores = ['#a78bfa', '#ec4899', '#3b8254', '#c084fc', '#f0abfc'];
        for (var i = 0; i < 16; i++) {
            var lazo = document.createElement('span');
            lazo.className = 'an-confeti';
            lazo.innerHTML = LAZO;
            var ang = (i / 16) * Math.PI * 2 + Math.random() * 0.4;
            var dist = 70 + Math.random() * 90;
            lazo.style.setProperty('--x', (Math.cos(ang) * dist).toFixed(0) + 'px');
            lazo.style.setProperty('--y', (Math.sin(ang) * dist - 30).toFixed(0) + 'px');
            lazo.style.setProperty('--r', (Math.random() * 540 - 270).toFixed(0) + 'deg');
            lazo.style.color = colores[i % colores.length];
            lazo.style.width = (12 + Math.random() * 10).toFixed(0) + 'px';
            lazo.style.animationDelay = (Math.random() * 0.15).toFixed(2) + 's';
            tarjeta.appendChild(lazo);
            lazo.addEventListener('animationend', function () { this.remove(); });
        }
    }

    /* =========== 5. Error =========== */
    function iniciarError() {
        var alerta = document.querySelector('#uploadForm') &&
                     document.querySelector('.alert-danger');
        if (!alerta) return;

        alerta.classList.add('an-error');
        var zona = document.getElementById('dropzone');
        if (zona) zona.classList.add('an-reintentar');

        if (!reducir && alerta.getBoundingClientRect().top > window.innerHeight * 0.6) {
            setTimeout(function () { alerta.scrollIntoView({ behavior: 'smooth', block: 'center' }); }, 250);
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', iniciar);
    } else {
        iniciar();
    }
})();
