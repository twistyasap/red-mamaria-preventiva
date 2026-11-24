import json
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from .services import sonia_ia


class RespuestaFalsa:
    """Imita una respuesta de requests con stream=True."""

    def __init__(self, status_code=200, eventos=None, error=None):
        self.status_code = status_code
        self.eventos = eventos or []
        self.error = error
        self.text = json.dumps(error or {})

    def iter_lines(self):
        for evento in self.eventos:
            yield b'data: ' + json.dumps(evento).encode()
            yield b''
        yield b'data: [DONE]'

    def json(self):
        return self.error or {}

    def close(self):
        pass


def evento_groq(texto):
    return {'choices': [{'delta': {'content': texto}}]}


def evento_gemini(texto):
    return {'candidates': [{'content': {'parts': [{'text': texto}]}}]}


CLAVES = dict(
    GROQ_API_KEY='groq-test',
    GROQ_MODELS=['openai/gpt-oss-120b'],
    GEMINI_API_KEY='gemini-test',
    GEMINI_MODELS=['gemini-3.1-flash-lite', 'gemma-4-26b-a4b-it'],
    SONIA_MOSTRAR_ERRORES=False,
)


@override_settings(**CLAVES)
class SoniaIATests(TestCase):

    def generar(self, respuestas):
        """Ejecuta generar_respuesta con requests.post simulado."""

        with mock.patch.object(
            sonia_ia.requests, 'post', side_effect=respuestas
        ) as post:
            eventos = list(
                sonia_ia.generar_respuesta([], '¿Qué es una mamografía?')
            )

        return eventos, post

    def test_usa_groq_primero_y_entrega_trozos(self):

        eventos, post = self.generar([
            RespuestaFalsa(eventos=[evento_groq('Una '), evento_groq('mamografía')]),
        ])

        self.assertEqual(eventos, [
            ('texto', 'Una '),
            ('texto', 'mamografía'),
            ('fin', {'respaldo': False}),
        ])
        self.assertIn('api.groq.com', post.call_args.args[0])
        payload = post.call_args.kwargs['json']
        self.assertTrue(payload['stream'])
        self.assertEqual(payload['reasoning_effort'], 'low')
        self.assertFalse(payload['include_reasoning'])
        self.assertEqual(payload['messages'][0]['role'], 'system')
        self.assertEqual(payload['messages'][-1], {
            'role': 'user', 'content': '¿Qué es una mamografía?'
        })

    def test_si_groq_esta_saturado_pasa_a_gemini_sin_esperas(self):

        eventos, post = self.generar([
            RespuestaFalsa(429, error={'error': {'message': 'Rate limit'}}),
            RespuestaFalsa(eventos=[evento_gemini('Hola')]),
        ])

        self.assertEqual(eventos[0], ('texto', 'Hola'))
        self.assertEqual(eventos[-1], ('fin', {'respaldo': False}))
        url_gemini = post.call_args.args[0]
        self.assertIn('gemini-3.1-flash-lite:streamGenerateContent', url_gemini)
        config = post.call_args.kwargs['json']['generationConfig']
        self.assertEqual(config['thinkingConfig'], {'thinkingLevel': 'minimal'})

    def test_gemma_no_recibe_config_de_razonamiento(self):

        self.assertIsNone(
            sonia_ia._config_razonamiento_gemini('gemma-4-26b-a4b-it')
        )

    def test_clave_invalida_salta_los_demas_modelos_del_proveedor(self):

        eventos, post = self.generar([
            RespuestaFalsa(429, error={'error': {'message': 'Rate limit'}}),
            RespuestaFalsa(403, error={'error': {'message': 'API key not valid'}}),
        ])

        # Groq + un solo Gemini: el segundo Gemini no se intenta
        self.assertEqual(post.call_count, 2)
        self.assertEqual(eventos[-1], ('fin', {'respaldo': True}))

    def test_si_nadie_responde_usa_respaldo(self):

        eventos, post = self.generar([
            RespuestaFalsa(503, error={'error': {'message': 'Overloaded'}}),
            RespuestaFalsa(503, error={'error': {'message': 'Overloaded'}}),
            RespuestaFalsa(eventos=[]),  # respuesta vacía
        ])

        self.assertEqual(post.call_count, 3)
        self.assertEqual(eventos[0][0], 'texto')
        self.assertTrue(eventos[0][1])
        self.assertEqual(eventos[-1], ('fin', {'respaldo': True}))

    def test_corte_a_la_mitad_deja_lo_escrito(self):

        class RespuestaCortada(RespuestaFalsa):
            def iter_lines(self):
                yield b'data: ' + json.dumps(evento_groq('Parte 1')).encode()
                raise sonia_ia.requests.exceptions.ChunkedEncodingError('corte')

        eventos, post = self.generar([RespuestaCortada()])

        self.assertEqual(post.call_count, 1)
        self.assertEqual(eventos, [
            ('texto', 'Parte 1'),
            ('fin', {'respaldo': False, 'incompleta': True}),
        ])

    def test_armar_conversacion_alterna_roles(self):

        historial = [
            {'rol': 'sonia', 'texto': 'saludo suelto'},
            {'rol': 'usuario', 'texto': 'pregunta 1'},
            {'rol': 'sonia', 'texto': 'respuesta 1'},
            {'rol': 'usuario', 'texto': 'sin respuesta'},
            {'rol': 'hacker', 'texto': 'ignorar'},
            'basura',
        ]

        conversacion = sonia_ia.armar_conversacion(historial, 'pregunta 2')

        self.assertEqual(
            [item['rol'] for item in conversacion],
            ['user', 'assistant', 'user']
        )
        self.assertEqual(conversacion[-1]['texto'], 'pregunta 2')


@override_settings(**CLAVES)
class VistaSoniaTests(TestCase):

    def setUp(self):
        User.objects.create_user('ana', password='clave-segura-123')
        self.client.login(username='ana', password='clave-segura-123')
        self.url = reverse('asistente_virtual_mensaje')

    def enviar(self, cuerpo):
        return self.client.post(
            self.url, json.dumps(cuerpo), content_type='application/json'
        )

    def test_responde_en_streaming_ndjson(self):

        with mock.patch.object(sonia_ia.requests, 'post', return_value=RespuestaFalsa(
            eventos=[evento_groq('Hola '), evento_groq('Ana')]
        )):
            response = self.enviar({'mensaje': 'hola', 'historial': []})
            lineas = b''.join(response.streaming_content).decode().splitlines()

        self.assertEqual(response.status_code, 200)
        self.assertIn('ndjson', response['Content-Type'])
        self.assertEqual(
            [json.loads(linea) for linea in lineas],
            [{'texto': 'Hola '}, {'texto': 'Ana'}, {'fin': True, 'respaldo': False}]
        )

    def test_mensaje_vacio(self):

        self.assertEqual(self.enviar({'mensaje': '   '}).status_code, 400)
        self.assertEqual(self.enviar(['no', 'es', 'objeto']).status_code, 400)

    @override_settings(GROQ_API_KEY='', GEMINI_API_KEY='')
    def test_sin_claves_responde_error(self):

        response = self.enviar({'mensaje': 'hola'})

        self.assertEqual(response.status_code, 500)
        self.assertTrue(response.json()['es_error'])
