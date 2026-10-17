"""Pruebas del modulo de Docentes.

Se ejecutan con:
    python manage.py test docentes

Usan una base de datos de prueba aparte, asi que no tocan los datos reales.
"""

import json
from datetime import timedelta
from pathlib import Path

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Actividad, Asistencia, Sesion, SolicitudRecuperacion, Usuario

CORREO = 'docente@test.local'
CODIGO = 'DOC-9999'
CLAVE = 'ClaveSegura2026*'


class BaseModuloDocentes(TestCase):
    """Datos comunes: un docente, un estudiante y una brigada con horas."""

    @classmethod
    def setUpTestData(cls):
        cls.docente = Usuario.objects.create_user(
            correo=CORREO,
            password=CLAVE,
            nombre_completo='Docente de Prueba',
            codigo=CODIGO,
            rol=Usuario.ROL_PROFESOR,
        )
        cls.estudiante = Usuario.objects.create_user(
            correo='alumno@test.local',
            password=CLAVE,
            nombre_completo='Alumno de Prueba',
            codigo='EST-9999',
            rol=Usuario.ROL_ESTUDIANTE,
        )
        cls.actividad = Actividad.objects.create(
            categoria=Actividad.CATEGORIA_GENERAL,
            nombre_actividad='Actividad de Prueba',
        )
        cls.sesion = Sesion.objects.create(
            id_profesor=cls.docente,
            id_tipo=cls.actividad,
            fecha_hora=timezone.now() + timedelta(days=1),
            ubicacion='Salon 1',
            cupos_max=10,
            cupos_disponibles=10,
        )
        Asistencia.objects.create(
            id_sesion=cls.sesion,
            id_estudiante=cls.estudiante,
            confirmacion=Asistencia.CONFIRMACION_ASISTE,
            validacion_prof=Asistencia.VALIDACION_CUMPLIDA,
            horas_ganadas=4,
        )


class ContrasenaTests(BaseModuloDocentes):
    """La contrasena nunca debe quedar en texto plano."""

    def test_se_guarda_cifrada(self):
        docente = Usuario.objects.get(correo=CORREO)
        self.assertTrue(docente.password.startswith('pbkdf2_'))
        self.assertNotIn(CLAVE, docente.password)
        self.assertTrue(docente.check_password(CLAVE))

    def test_rechaza_clave_incorrecta(self):
        docente = Usuario.objects.get(correo=CORREO)
        self.assertFalse(docente.check_password('otra-clave'))


class LoginTests(BaseModuloDocentes):
    """Flujo de inicio de sesion."""

    def test_login_correcto_redirige_al_panel(self):
        respuesta = self.client.post(
            reverse('docentes:login'),
            {'identificador': CORREO, 'password': CLAVE},
        )
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(respuesta['Location'], reverse('docentes:dashboard'))

    def test_login_con_el_codigo_academico(self):
        respuesta = self.client.post(
            reverse('docentes:login'),
            {'identificador': CODIGO, 'password': CLAVE},
        )
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(respuesta['Location'], reverse('docentes:dashboard'))

    def test_correo_no_distingue_mayusculas(self):
        respuesta = self.client.post(
            reverse('docentes:login'),
            {'identificador': CORREO.upper(), 'password': CLAVE},
        )
        self.assertEqual(respuesta.status_code, 302)

    def test_clave_mala_no_abre_sesion_y_suma_intento(self):
        respuesta = self.client.post(
            reverse('docentes:login'),
            {'identificador': CORREO, 'password': 'clave-incorrecta'},
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(
            Usuario.objects.get(correo=CORREO).intentos_fallidos,
            1,
        )

    def test_usuario_inexistente_no_revela_si_existe(self):
        respuesta = self.client.post(
            reverse('docentes:login'),
            {'identificador': 'nadie@test.local', 'password': 'lo-que-sea'},
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'incorrectos')

    def test_bloquea_la_cuenta_tras_cinco_intentos(self):
        for _ in range(5):
            self.client.post(
                reverse('docentes:login'),
                {'identificador': CORREO, 'password': 'clave-incorrecta'},
            )
        self.assertEqual(
            Usuario.objects.get(correo=CORREO).estado_cuenta,
            Usuario.ESTADO_BLOQUEADO,
        )

    def test_login_exitoso_reinicia_los_intentos(self):
        Usuario.objects.filter(correo=CORREO).update(intentos_fallidos=3)
        self.client.post(
            reverse('docentes:login'),
            {'identificador': CORREO, 'password': CLAVE},
        )
        self.assertEqual(
            Usuario.objects.get(correo=CORREO).intentos_fallidos,
            0,
        )


class PanelTests(BaseModuloDocentes):
    """El panel solo se ve con sesion y muestra el resumen real."""

    def test_requiere_sesion(self):
        respuesta = self.client.get(reverse('docentes:dashboard'))
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn('/login/', respuesta['Location'])

    def test_muestra_el_resumen_del_docente(self):
        self.client.login(username=CORREO, password=CLAVE)
        respuesta = self.client.get(reverse('docentes:dashboard'))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Docente de Prueba')
        self.assertContains(respuesta, 'Alumno de Prueba')
        # Una asistencia de 4 horas validadas.
        self.assertContains(respuesta, '4')


class RedireccionAbiertaTests(BaseModuloDocentes):
    """`next` no debe poder sacar al usuario del sitio."""

    def test_next_externo_se_descarta(self):
        respuesta = self.client.post(
            reverse('docentes:login') + '?next=https://sitio-malicioso.example',
            {'identificador': CORREO, 'password': CLAVE},
        )
        self.assertEqual(respuesta.status_code, 302)
        self.assertNotIn('sitio-malicioso', respuesta['Location'])
        self.assertEqual(respuesta['Location'], reverse('docentes:dashboard'))

    def test_next_interno_si_se_respeta(self):
        destino = reverse('docentes:cambiar_contrasena')
        respuesta = self.client.post(
            reverse('docentes:login') + f'?next={destino}',
            {'identificador': CORREO, 'password': CLAVE},
        )
        self.assertEqual(respuesta['Location'], destino)


class ApiLoginMaestroTests(BaseModuloDocentes):
    """Puente con el formulario HTML existente."""

    def test_autentica_y_redirige_al_panel(self):
        respuesta = self.client.post(
            reverse('api-login-maestro'),
            {'username': CORREO, 'password': CLAVE},
        )
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(respuesta['Location'], reverse('docentes:dashboard'))

    def test_clave_mala_vuelve_al_login(self):
        respuesta = self.client.post(
            reverse('api-login-maestro'),
            {'username': CORREO, 'password': 'clave-incorrecta'},
        )
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn('/login/', respuesta['Location'])


class RecuperarContrasenaTests(BaseModuloDocentes):
    """Formulario 'olvide mi contrasena'."""

    DATOS = {
        'usuario': CORREO,
        'nombre_completo': 'Docente de Prueba',
        'telefono': '3001234567',
        'asignatura': 'Matematicas',
    }

    def test_crea_solicitud_pendiente_y_vuelve_al_login(self):
        respuesta = self.client.post(reverse('docentes:recuperar'), self.DATOS)
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(respuesta['Location'], reverse('docentes:login'))
        solicitud = SolicitudRecuperacion.objects.get(usuario=CORREO)
        self.assertEqual(solicitud.estado, SolicitudRecuperacion.ESTADO_PENDIENTE)
        self.assertEqual(solicitud.asignatura, 'Matematicas')
        self.assertEqual(solicitud.telefono, '3001234567')

    def test_muestra_la_confirmacion_en_el_login(self):
        respuesta = self.client.post(
            reverse('docentes:recuperar'), self.DATOS, follow=True,
        )
        self.assertContains(respuesta, 'Solicitud registrada')

    def test_rechaza_un_telefono_invalido(self):
        datos = dict(self.DATOS, telefono='123')
        respuesta = self.client.post(reverse('docentes:recuperar'), datos)
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'telefono valido')
        self.assertFalse(SolicitudRecuperacion.objects.exists())

    def test_no_permite_dos_solicitudes_pendientes(self):
        self.client.post(reverse('docentes:recuperar'), self.DATOS)
        respuesta = self.client.post(reverse('docentes:recuperar'), self.DATOS)
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Ya existe una solicitud pendiente')
        self.assertEqual(SolicitudRecuperacion.objects.count(), 1)

    def test_la_pagina_ofrece_volver_al_login(self):
        respuesta = self.client.get(reverse('docentes:recuperar'))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, reverse('docentes:login'))


class RegistroTests(BaseModuloDocentes):
    """Registro de docentes con contrasena cifrada."""

    def test_registra_un_docente_con_clave_cifrada(self):
        respuesta = self.client.post(reverse('docentes:registro'), {
            'nombre_completo': 'Nuevo Docente',
            'correo': 'nuevo@test.local',
            'codigo': 'DOC-1111',
            'grado': 'Ciencias',
            'password1': 'ClaveNueva2026*',
            'password2': 'ClaveNueva2026*',
        })
        self.assertEqual(respuesta.status_code, 302)
        creado = Usuario.objects.get(correo='nuevo@test.local')
        self.assertEqual(creado.rol, Usuario.ROL_PROFESOR)
        self.assertTrue(creado.check_password('ClaveNueva2026*'))
        self.assertNotIn('ClaveNueva2026*', creado.password)

    def test_rechaza_correos_duplicados(self):
        respuesta = self.client.post(reverse('docentes:registro'), {
            'nombre_completo': 'Otro Docente',
            'correo': CORREO,
            'grado': '',
            'password1': 'ClaveNueva2026*',
            'password2': 'ClaveNueva2026*',
        })
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Ya existe una cuenta')


class ApiRecuperarContrasenaTests(BaseModuloDocentes):
    """Endpoint JSON que consume el formulario estatico de recuperacion."""

    def _ruta(self):
        return reverse('api-recuperar-contrasena-maestro')

    def _post(self, payload, **extra):
        return self.client.post(
            self._ruta(),
            data=json.dumps(payload),
            content_type='application/json',
            **extra,
        )

    def test_crea_la_solicitud_y_responde_success(self):
        respuesta = self._post({
            'usuario': CORREO,
            'nombre': 'Docente de Prueba',
            'telefono': '3001234567',
            'asignatura': 'Matematicas',
        })
        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.json()['success'])
        solicitud = SolicitudRecuperacion.objects.get(usuario=CORREO)
        # El HTML envia `nombre` y el modelo lo guarda en `nombre_completo`.
        self.assertEqual(solicitud.nombre_completo, 'Docente de Prueba')
        self.assertEqual(solicitud.asignatura, 'Matematicas')

    def test_telefono_corto_responde_400(self):
        respuesta = self._post({
            'usuario': CORREO,
            'nombre': 'Docente de Prueba',
            'telefono': '123',
            'asignatura': 'Matematicas',
        })
        self.assertEqual(respuesta.status_code, 400)
        self.assertFalse(respuesta.json()['success'])
        self.assertFalse(SolicitudRecuperacion.objects.exists())

    def test_json_invalido_responde_400(self):
        respuesta = self.client.post(
            self._ruta(), data='no soy json', content_type='application/json',
        )
        self.assertEqual(respuesta.status_code, 400)
        self.assertFalse(respuesta.json()['success'])

    def test_preflight_options_responde_204_con_cors(self):
        respuesta = self.client.options(
            self._ruta(), HTTP_ORIGIN='http://localhost:3000',
        )
        self.assertEqual(respuesta.status_code, 204)
        self.assertEqual(
            respuesta['Access-Control-Allow-Origin'], 'http://localhost:3000',
        )

    def test_origen_no_autorizado_no_recibe_cors(self):
        respuesta = self.client.options(
            self._ruta(), HTTP_ORIGIN='http://sitio-desconocido.example',
        )
        self.assertNotIn('Access-Control-Allow-Origin', respuesta)

    def test_el_post_exitoso_tambien_lleva_cors(self):
        respuesta = self._post({
            'usuario': CORREO,
            'nombre': 'Docente de Prueba',
            'telefono': '3001234567',
            'asignatura': 'Matematicas',
        }, HTTP_ORIGIN='http://localhost:3000')
        self.assertEqual(respuesta['Access-Control-Allow-Origin'], 'http://localhost:3000')


class PaginasEstaticasConectadasTests(TestCase):
    """
    Guarda contra la regresion: si alguien vuelve a dejar las paginas
    decoradas apuntando a las rutas muertas de server.js, vuelven los 404.
    """

    RAIZ = Path(__file__).resolve().parents[2]

    def _leer(self, carpeta):
        return (self.RAIZ / carpeta / 'index.html').read_text(encoding='utf-8')

    def test_login_apunta_al_backend_de_django(self):
        html = self._leer('login_maestro_horasocial_pro')
        self.assertIn('action="http://127.0.0.1:8000/api/login-maestro"', html)
        self.assertNotIn('action="/api/login-maestro"', html)

    def test_recuperacion_apunta_al_backend_de_django(self):
        html = self._leer('recuperar_contrasena_maestro_horasocial_pro')
        self.assertIn("fetch(API_BASE + '/api/recuperar-contrasena-maestro'", html)
        self.assertNotIn("fetch('/api/recuperar-contrasena-maestro'", html)
