"""Pruebas del modulo de Docentes.

Se ejecutan con:
    python manage.py test docentes

Usan una base de datos de prueba aparte, asi que no tocan los datos reales.
"""

import json
import shutil
import tempfile
from datetime import date, time, timedelta
from pathlib import Path

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import (
    Actividad,
    Asistencia,
    Sesion,
    SolicitudRecuperacion,
    Usuario,
    SesionServicio,
)

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

    @override_settings(DASHBOARD_DOCENTE_URL='')
    def test_autentica_y_redirige_al_panel(self):
        """Sin frontend decorado configurado, el login va al panel de Django."""
        respuesta = self.client.post(
            reverse('api-login-maestro'),
            {'username': CORREO, 'password': CLAVE},
        )
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(respuesta['Location'], reverse('docentes:dashboard'))

    def test_autentica_y_redirige_al_dashboard_decorado(self):
        """Con el frontend decorado configurado, el login aterriza alli."""
        respuesta = self.client.post(
            reverse('api-login-maestro'),
            {'username': CORREO, 'password': CLAVE},
        )
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(respuesta['Location'], settings.DASHBOARD_DOCENTE_URL)

    def test_clave_mala_vuelve_al_login_decorado(self):
        """Un intento fallido vuelve al formulario decorado, no a Django.

        Antes rebotaba a `docentes:login`, una pantalla plana que ofrece
        "olvide mi contrasena": el docente creia que lo habian mandado al
        formulario de recuperacion.
        """
        respuesta = self.client.post(
            reverse('api-login-maestro'),
            {'username': CORREO, 'password': 'clave-incorrecta'},
        )
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(
            respuesta['Location'],
            settings.LOGIN_DOCENTE_URL + '?error=credenciales',
        )
        self.assertNotIn('_auth_user_id', self.client.session)

    @override_settings(LOGIN_DOCENTE_URL='')
    def test_clave_mala_vuelve_al_login_de_django_sin_frontend(self):
        """Sin frontend decorado configurado cae al login de Django."""
        respuesta = self.client.post(
            reverse('api-login-maestro'),
            {'username': CORREO, 'password': 'clave-incorrecta'},
        )
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(respuesta['Location'], reverse('docentes:login'))
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_datos_incompletos_vuelven_al_login_decorado(self):
        """Un formulario vacio no debe aterrizar en las pantallas de Django."""
        respuesta = self.client.post(
            reverse('api-login-maestro'),
            {'username': '', 'password': ''},
        )
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(
            respuesta['Location'],
            settings.LOGIN_DOCENTE_URL + '?error=credenciales',
        )


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


class ApiRestablecerContrasenaTests(BaseModuloDocentes):
    """
    Paso 2 del formulario decorado: fija la contrasena nueva.

    Prueba que la clave quede cifrada en `usuariosa`, que la solicitud pase a
    'Restablecida' y que un tercero no pueda entrar solo con adivinar el
    codigo: el nombre tiene que coincidir con el de la cuenta.
    """

    NUEVA_CLAVE = 'NuevaClave2026*'

    def _ruta(self):
        return reverse('api-restablecer-contrasena-maestro')

    def _post(self, payload, **extra):
        return self.client.post(
            self._ruta(),
            data=json.dumps(payload),
            content_type='application/json',
            **extra,
        )

    def _payload(self, **cambios):
        payload = {
            'usuario': CODIGO,
            'nombre': 'Docente de Prueba',
            'telefono': '3001234567',
            'asignatura': 'Matematicas',
            'password1': self.NUEVA_CLAVE,
            'password2': self.NUEVA_CLAVE,
        }
        payload.update(cambios)
        return payload

    def _enviar_paso_1(self):
        return self.client.post(
            reverse('api-recuperar-contrasena-maestro'),
            data=json.dumps({
                'usuario': CODIGO,
                'nombre': 'Docente de Prueba',
                'telefono': '3001234567',
                'asignatura': 'Matematicas',
            }),
            content_type='application/json',
        )

    def test_cambia_la_clave_y_responde_success(self):
        respuesta = self._post(self._payload())
        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.json()['success'])
        docente = Usuario.objects.get(pk=self.docente.pk)
        self.assertTrue(docente.check_password(self.NUEVA_CLAVE))
        self.assertFalse(docente.check_password(CLAVE))

    def test_guarda_el_hash_y_nunca_el_texto_plano(self):
        self._post(self._payload())
        guardado = Usuario.objects.get(pk=self.docente.pk).password
        self.assertTrue(guardado.startswith('pbkdf2_'))
        self.assertNotIn(self.NUEVA_CLAVE, guardado)

    def test_cierra_la_solicitud_del_paso_1_como_restablecida(self):
        self._enviar_paso_1()
        self.assertEqual(SolicitudRecuperacion.objects.count(), 1)
        self._post(self._payload())
        solicitud = SolicitudRecuperacion.objects.get(usuario=CODIGO)
        self.assertEqual(solicitud.estado, SolicitudRecuperacion.ESTADO_RESTABLECIDA)
        self.assertIsNotNone(solicitud.fecha_resolucion)

    def test_sin_paso_1_crea_la_solicitud_ya_resuelta(self):
        """El paso 2 se puede repetir tras recargar la pagina."""
        self._post(self._payload())
        self.assertEqual(SolicitudRecuperacion.objects.count(), 1)
        solicitud = SolicitudRecuperacion.objects.get()
        self.assertEqual(solicitud.estado, SolicitudRecuperacion.ESTADO_RESTABLECIDA)
        self.assertEqual(solicitud.telefono, '3001234567')

    def test_un_nombre_distinto_no_puede_cambiar_la_clave(self):
        """Codigo + nombre es la prueba de identidad: el nombre falla, nada se escribe."""
        respuesta = self._post(self._payload(nombre='Otra Persona'))
        self.assertEqual(respuesta.status_code, 403)
        self.assertFalse(respuesta.json()['success'])
        self.assertTrue(Usuario.objects.get(pk=self.docente.pk).check_password(CLAVE))
        self.assertFalse(SolicitudRecuperacion.objects.exists())

    def test_el_nombre_no_distingue_mayusculas_ni_tildes(self):
        respuesta = self._post(self._payload(nombre='  docente DE   prueba '))
        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(
            Usuario.objects.get(pk=self.docente.pk).check_password(self.NUEVA_CLAVE),
        )

    def test_un_identificador_inexistente_no_revela_si_existe(self):
        respuesta = self._post(self._payload(usuario='nadie@test.local'))
        otra = self._post(self._payload(usuario=CODIGO, nombre='Otra Persona'))
        self.assertEqual(respuesta.status_code, 403)
        self.assertEqual(respuesta.json()['error'], otra.json()['error'])

    def test_un_estudiante_no_puede_restablecer(self):
        respuesta = self._post(self._payload(
            usuario='EST-9999',
            nombre='Alumno de Prueba',
        ))
        self.assertEqual(respuesta.status_code, 403)
        self.assertTrue(
            Usuario.objects.get(pk=self.estudiante.pk).check_password(CLAVE),
        )

    def test_claves_distintas_responden_400(self):
        respuesta = self._post(self._payload(password2='OtraClave2026*'))
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn('coinciden', respuesta.json()['error'])
        self.assertTrue(Usuario.objects.get(pk=self.docente.pk).check_password(CLAVE))

    def test_clave_solo_numerica_responde_400(self):
        respuesta = self._post(self._payload(
            password1='12345678', password2='12345678',
        ))
        self.assertEqual(respuesta.status_code, 400)
        self.assertFalse(Usuario.objects.get(pk=self.docente.pk).check_password('12345678'))

    def test_telefono_corto_responde_400(self):
        respuesta = self._post(self._payload(telefono='123'))
        self.assertEqual(respuesta.status_code, 400)
        self.assertFalse(SolicitudRecuperacion.objects.exists())

    def test_json_invalido_responde_400(self):
        respuesta = self.client.post(
            self._ruta(), data='no soy json', content_type='application/json',
        )
        self.assertEqual(respuesta.status_code, 400)
        self.assertFalse(respuesta.json()['success'])

    def test_libera_una_cuenta_bloqueada_por_intentos(self):
        """Quien recupera la clave vuelve a poder entrar aunque este bloqueada."""
        Usuario.objects.filter(pk=self.docente.pk).update(
            intentos_fallidos=5,
            estado_cuenta=Usuario.ESTADO_BLOQUEADO,
        )
        self._post(self._payload())
        docente = Usuario.objects.get(pk=self.docente.pk)
        self.assertEqual(docente.estado_cuenta, Usuario.ESTADO_ACTIVO)
        self.assertEqual(docente.intentos_fallidos, 0)

    def test_preflight_options_responde_204_con_cors(self):
        respuesta = self.client.options(
            self._ruta(), HTTP_ORIGIN='http://localhost:3000',
        )
        self.assertEqual(respuesta.status_code, 204)
        self.assertEqual(
            respuesta['Access-Control-Allow-Origin'], 'http://localhost:3000',
        )

    def test_el_post_exitoso_tambien_lleva_cors(self):
        respuesta = self._post(self._payload(), HTTP_ORIGIN='http://127.0.0.1:3000')
        self.assertEqual(
            respuesta['Access-Control-Allow-Origin'], 'http://127.0.0.1:3000',
        )

    def test_con_ese_nuevo_login_se_abre_el_panel(self):
        """El flujo completo: clave nueva -> login -> dashboard."""
        self._post(self._payload())
        respuesta = self.client.post(
            reverse('docentes:login'),
            {'identificador': CODIGO, 'password': self.NUEVA_CLAVE},
        )
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(respuesta['Location'], reverse('docentes:dashboard'))


class ApiSesionActualTests(BaseModuloDocentes):
    """
    Quien tiene la sesion abierta.

    Es lo que consulta el dashboard decorado para saludar al docente real y
    para no quedar accesible sin login.
    """

    def _ruta(self):
        return reverse('api-sesion-actual')

    def _get(self, **extra):
        return self.client.get(self._ruta(), **extra)

    def test_sin_sesion_responde_no_autenticado(self):
        respuesta = self._get()
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(respuesta.json()['autenticado'])

    def test_con_sesion_devuelve_los_datos_del_docente(self):
        self.client.login(username=CORREO, password=CLAVE)
        respuesta = self._get()
        self.assertEqual(respuesta.status_code, 200)
        datos = respuesta.json()
        self.assertTrue(datos['autenticado'])
        self.assertEqual(datos['nombre'], self.docente.nombre_completo)
        self.assertEqual(datos['correo'], CORREO)
        self.assertTrue(datos['es_docente'])

    def test_responde_con_credenciales_para_el_fetch_cross_origin(self):
        """
        El fetch del dashboard va con `credentials: 'include'`. Sin
        Access-Control-Allow-Credentials el navegador descarta la respuesta y
        el panel nunca reconoceria la sesion.
        """
        respuesta = self._get(HTTP_ORIGIN='http://127.0.0.1:3000')
        self.assertEqual(
            respuesta['Access-Control-Allow-Origin'], 'http://127.0.0.1:3000',
        )
        self.assertEqual(respuesta['Access-Control-Allow-Credentials'], 'true')

    def test_origen_no_autorizado_no_recibe_cors(self):
        respuesta = self._get(HTTP_ORIGIN='http://sitio-desconocido.example')
        self.assertNotIn('Access-Control-Allow-Origin', respuesta)

    def test_preflight_options_responde_204(self):
        respuesta = self.client.options(
            self._ruta(), HTTP_ORIGIN='http://127.0.0.1:3000',
        )
        self.assertEqual(respuesta.status_code, 204)


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

    def test_recuperacion_ofrece_el_paso_de_la_clave_nueva(self):
        """
        Enviar la solicitud tiene que abrir el recuadro para escribir la clave
        nueva, y ese recuadro tiene que apuntar al segundo endpoint del
        backend (rutas absolutas, nunca relativas a server.js).
        """
        html = self._leer('recuperar_contrasena_maestro_horasocial_pro')
        self.assertIn('id="passwordForm"', html)
        self.assertIn('id="password1"', html)
        self.assertIn('id="password2"', html)
        self.assertIn(
            "fetch(API_BASE + '/api/restablecer-contrasena-maestro'", html,
        )
        self.assertNotIn(
            "fetch('/api/restablecer-contrasena-maestro'", html,
        )

    def test_el_dashboard_consulta_la_sesion_del_backend(self):
        """
        El panel decorado no muestra el placeholder de la maqueta: pregunta
        por la sesion real y se protege si no hay ninguna abierta.
        """
        html = self._leer('dashboard_maestro_horasocial_pro')
        self.assertIn("fetch(API + '/api/sesion-actual'", html)
        self.assertIn("credentials: 'include'", html)
        self.assertIn("/profesor/login", html)

    def test_el_dashboard_avisa_cuando_no_hay_sesion(self):
        """
        Sin sesion, el panel vuelve al login con la marca de error para que el
        docente vea el aviso en el formulario decorado.
        """
        html = self._leer('dashboard_maestro_horasocial_pro')
        self.assertIn('/profesor/login?error=sesion', html)

    def test_el_login_muestra_el_aviso_de_error_en_la_propia_pagina(self):
        """
        El formulario decorado lee `?error=` y muestra el aviso ahi mismo, en
        vez de dejar que el docente aterrice en las pantallas planas de Django.
        """
        html = self._leer('login_maestro_horasocial_pro')
        self.assertIn('id="loginError"', html)
        self.assertIn("get('error')", html)


class ApiPanelMaestroTests(BaseModuloDocentes):
    """
    Panel del docente con datos reales: dashboard, validacion y reporte.

    Los tres endpoints exigen sesion de docente. El panel refleja los
    contadores reales de las asistencias, valida solo registros del alcance
    del docente y el reporte respeta la forma semanal/mensual.
    """

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.estudiante2 = Usuario.objects.create_user(
            correo='alumno2@test.local',
            password=CLAVE,
            nombre_completo='Segundo Alumno',
            codigo='EST-9998',
            rol=Usuario.ROL_ESTUDIANTE,
        )
        # Una asistencia pendiente en la sesion del docente base...
        cls.pendiente = Asistencia.objects.create(
            id_sesion=cls.sesion,
            id_estudiante=cls.estudiante2,
            confirmacion=Asistencia.CONFIRMACION_ASISTE,
            validacion_prof=Asistencia.VALIDACION_POR_VALIDAR,
            horas_ganadas=4,
            fecha_confirmacion=timezone.now(),
        )
        # ...y la ya validada, fechada hoy para que entre en el periodo del
        # reporte semanal.
        Asistencia.objects.filter(
            id_sesion=cls.sesion,
            id_estudiante=cls.estudiante,
        ).update(fecha_confirmacion=timezone.now())

        # Un segundo docente con su propia sesion y asistencia: sirve para
        # probar que nadie valida registros ajenos.
        cls.otro_docente = Usuario.objects.create_user(
            correo='otro@test.local',
            password=CLAVE,
            nombre_completo='Otro Docente',
            codigo='DOC-8888',
            rol=Usuario.ROL_PROFESOR,
        )
        cls.otra_sesion = Sesion.objects.create(
            id_profesor=cls.otro_docente,
            id_tipo=cls.actividad,
            fecha_hora=timezone.now() + timedelta(days=2),
            ubicacion='Salon 9',
            cupos_max=10,
            cupos_disponibles=10,
        )
        cls.otra_asistencia = Asistencia.objects.create(
            id_sesion=cls.otra_sesion,
            id_estudiante=cls.estudiante,
            confirmacion=Asistencia.CONFIRMACION_ASISTE,
            validacion_prof=Asistencia.VALIDACION_POR_VALIDAR,
            horas_ganadas=4,
            fecha_confirmacion=timezone.now(),
        )

    def _dashboard(self, **extra):
        return self.client.get(reverse('api-dashboard-maestro'), **extra)

    def _accion(self, payload, **extra):
        return self.client.post(
            reverse('api-asistencia-accion'),
            data=json.dumps(payload),
            content_type='application/json',
            **extra,
        )

    def _reporte(self, tipo):
        return self.client.get(reverse('api-reporte-maestro'), {'tipo': tipo})

    def _abrir_sesion(self):
        self.client.login(username=CORREO, password=CLAVE)

    def test_sin_sesion_los_endpoints_del_panel_responden_401(self):
        casos = [
            ('dashboard', self._dashboard()),
            ('estudiantes', self._estudiantes()),
            ('sesionservicio', self._sesionservicio()),
            ('sesionservicio_accion', self._sesionservicio_accion(
                {'id_registro': 1, 'accion': 'completar'},
            )),
            ('accion', self._accion(
                {'id_registro': self.pendiente.pk, 'accion': 'aprobar'},
            )),
            ('reporte', self._reporte('semanal')),
        ]
        for nombre, respuesta in casos:
            with self.subTest(endpoint=nombre):
                self.assertEqual(respuesta.status_code, 401)
                self.assertEqual(
                    respuesta.json(),
                    {'autenticado': False, 'error': 'sesion'},
                )

    def test_el_dashboard_entrega_las_claves_y_los_contadores_reales(self):
        self._abrir_sesion()
        respuesta = self._dashboard()
        self.assertEqual(respuesta.status_code, 200)
        datos = respuesta.json()

        self.assertTrue(datos['autenticado'])
        self.assertEqual(datos['docente']['nombre'], self.docente.nombre_completo)
        self.assertEqual(
            datos['stats'],
            {
                # Los dos alumnos con asistencia en la sesion del docente.
                'estudiantes': 2,
                'actividades': 1,
                # La asistencia validada 'Cumplida' de 4 horas.
                'horas_totales': 4,
                'pendientes': 1,
            },
        )

        self.assertEqual(len(datos['brigadas']), 1)
        brigada = datos['brigadas'][0]
        self.assertEqual(brigada['nombre'], self.actividad.nombre_actividad)
        self.assertEqual(brigada['estudiantes'], 2)
        self.assertEqual(brigada['horas'], 4)
        self.assertEqual(brigada['meta'], 10)
        self.assertEqual(brigada['pct'], 40)
        self.assertIsNotNone(brigada['proxima'])

        self.assertEqual(len(datos['pendientes']), 1)
        fila = datos['pendientes'][0]
        self.assertEqual(fila['id_registro'], self.pendiente.pk)
        self.assertEqual(fila['estudiante'], self.estudiante2.nombre_completo)
        self.assertEqual(fila['actividad'], self.actividad.nombre_actividad)
        self.assertEqual(fila['ubicacion'], self.sesion.ubicacion)
        self.assertEqual(fila['confirmacion'], Asistencia.CONFIRMACION_ASISTE)

        self.assertGreaterEqual(len(datos['notifs']), 2)
        self.assertLessEqual(len(datos['notifs']), 4)
        for aviso in datos['notifs']:
            self.assertEqual(set(aviso), {'id', 'txt', 'hora', 'leido'})

    def _estudiantes(self, **extra):
        return self.client.get(reverse('api-estudiantes-maestro'), **extra)

    def _sesionservicio(self, **extra):
        return self.client.get(reverse('api-sesionservicio-maestro'), **extra)

    def _sesionservicio_accion(self, payload, **extra):
        return self.client.post(
            reverse('api-sesionservicio-accion'),
            data=json.dumps(payload),
            content_type='application/json',
            **extra,
        )

    def _registrar_sesionservicio(self, **datos):
        """Registra una actividad por el mismo camino que usa el formulario."""
        payload = {
            'titulo': 'Seguridad en el taller',
            'taller': 'Taller 1',
            'fecha': (timezone.localdate() + timedelta(days=3)).isoformat(),
            'hora': '08:30',
            'duracion': '2 h',
            'nota': 'Llevar guantes',
            'estudiantes': [self.estudiante.pk, self.estudiante2.pk],
        }
        payload.update(datos)
        return self.client.post(reverse('api-sesionservicio-maestro'), data=payload)

    def test_la_pantalla_de_estudiantes_tiene_la_forma_esperada(self):
        self._abrir_sesion()
        respuesta = self._estudiantes()
        self.assertEqual(respuesta.status_code, 200)
        datos = respuesta.json()

        self.assertTrue(datos['autenticado'])
        self.assertEqual(datos['docente']['nombre'], self.docente.nombre_completo)
        self.assertEqual(
            datos['stats'],
            # Un alumno ya validado (4 h) y otro esperando validacion.
            {'total': 2, 'al_dia': 1, 'horas': 4, 'meta': 80},
        )

        self.assertEqual(len(datos['estudiantes']), 2)
        for fila in datos['estudiantes']:
            self.assertEqual(
                set(fila),
                {
                    'id', 'nombre', 'codigo', 'correo', 'grado', 'brigada',
                    'horas', 'pendientes', 'meta', 'pct', 'estado', 'historial',
                },
            )
            self.assertEqual(fila['meta'], 80)

    def test_el_estudiante_validado_queda_al_dia_y_el_pendiente_no(self):
        self._abrir_sesion()
        por_codigo = {
            fila['codigo']: fila
            for fila in self._estudiantes().json()['estudiantes']
        }

        al_dia = por_codigo[self.estudiante.codigo]
        self.assertEqual(al_dia['estado'], 'Al dia')
        self.assertEqual(al_dia['horas'], 4)
        self.assertEqual(al_dia['pendientes'], 0)
        self.assertEqual(al_dia['historial'][0]['h'], 4)

        esperando = por_codigo[self.estudiante2.codigo]
        self.assertEqual(esperando['estado'], 'Pendiente')
        self.assertEqual(esperando['horas'], 0)
        self.assertEqual(esperando['pendientes'], 1)

    def test_las_dos_pantallas_muestran_los_mismos_numeros(self):
        """El panel y la pantalla de estudiantes no pueden divergir."""
        self._abrir_sesion()
        panel = self._dashboard().json()['stats']
        estudiantes = self._estudiantes().json()['stats']

        self.assertEqual(estudiantes['total'], panel['estudiantes'])
        self.assertEqual(estudiantes['horas'], panel['horas_totales'])

    def test_aprobar_en_el_panel_se_refleja_en_la_pantalla_de_estudiantes(self):
        """Validar una asistencia actualiza las dos pantallas a la vez."""
        self._abrir_sesion()
        antes = self._estudiantes().json()['stats']
        self.assertEqual(antes['al_dia'], 1)

        self._accion({'id_registro': self.pendiente.pk, 'accion': 'aprobar'})

        despues = self._estudiantes().json()['stats']
        self.assertEqual(despues['al_dia'], 2)
        self.assertEqual(despues['horas'], antes['horas'] + 4)
        # Y el panel ya no tiene pendientes que validar.
        self.assertEqual(self._dashboard().json()['stats']['pendientes'], 0)

    def test_un_docente_sin_sesiones_ve_arreglos_vacios(self):
        """Los estados vacios del panel son arreglos, nunca null."""
        vacio = Usuario.objects.create_user(
            correo='vacio@test.local',
            password=CLAVE,
            nombre_completo='Docente Sin Sesiones',
            codigo='DOC-7777',
            rol=Usuario.ROL_PROFESOR,
        )
        self.client.login(username=vacio.correo, password=CLAVE)
        datos = self._dashboard().json()
        self.assertEqual(datos['brigadas'], [])
        self.assertEqual(datos['pendientes'], [])
        self.assertEqual(
            datos['stats'],
            {'estudiantes': 0, 'actividades': 0, 'horas_totales': 0, 'pendientes': 0},
        )
        self.assertGreaterEqual(len(datos['notifs']), 2)

    def test_aprobar_valida_la_asistencia_y_baja_los_pendientes(self):
        self._abrir_sesion()
        pendientes_antes = self._dashboard().json()['stats']['pendientes']

        respuesta = self._accion({
            'id_registro': self.pendiente.pk,
            'accion': 'aprobar',
            'horas': 3,
        })
        self.assertEqual(respuesta.status_code, 200)
        datos = respuesta.json()
        self.assertTrue(datos['success'])
        self.assertEqual(datos['stats']['pendientes'], pendientes_antes - 1)
        self.assertEqual(datos['stats']['horas_totales'], 4 + 3)

        self.pendiente.refresh_from_db()
        self.assertEqual(self.pendiente.validacion_prof, Asistencia.VALIDACION_CUMPLIDA)
        self.assertEqual(self.pendiente.horas_ganadas, 3)

    def test_las_horas_se_acotan_a_0_24(self):
        self._abrir_sesion()
        self._accion({
            'id_registro': self.pendiente.pk,
            'accion': 'aprobar',
            'horas': 99,
        })
        self.pendiente.refresh_from_db()
        self.assertEqual(self.pendiente.horas_ganadas, 24)

    def test_rechazar_marca_inasistencia_sin_horas(self):
        self._abrir_sesion()
        respuesta = self._accion({
            'id_registro': self.pendiente.pk,
            'accion': 'rechazar',
        })
        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.json()['success'])

        self.pendiente.refresh_from_db()
        self.assertEqual(
            self.pendiente.validacion_prof, Asistencia.VALIDACION_INASISTENCIA,
        )
        self.assertEqual(self.pendiente.horas_ganadas, 0)

    def test_no_se_puede_validar_una_asistencia_de_otro_docente(self):
        self._abrir_sesion()
        respuesta = self._accion({
            'id_registro': self.otra_asistencia.pk,
            'accion': 'aprobar',
        })
        self.assertEqual(respuesta.status_code, 403)
        self.assertEqual(respuesta.json(), {'success': False, 'error': 'no autorizado'})

        self.otra_asistencia.refresh_from_db()
        self.assertEqual(
            self.otra_asistencia.validacion_prof, Asistencia.VALIDACION_POR_VALIDAR,
        )

    def test_el_reporte_semanal_y_mensual_tienen_su_forma(self):
        self._abrir_sesion()
        for tipo, dias in (('semanal', 7), ('mensual', 30)):
            with self.subTest(tipo=tipo):
                respuesta = self._reporte(tipo)
                self.assertEqual(respuesta.status_code, 200)
                datos = respuesta.json()

                self.assertEqual(datos['tipo'], tipo)
                self.assertEqual(sorted(datos['periodo']), ['desde', 'hasta'])
                desde = date.fromisoformat(datos['periodo']['desde'])
                hasta = date.fromisoformat(datos['periodo']['hasta'])
                self.assertEqual(hasta, timezone.localdate())
                self.assertEqual((hasta - desde).days, dias - 1)

                self.assertEqual(datos['resumen']['estudiantes'], 2)
                self.assertEqual(datos['resumen']['actividades'], 1)
                self.assertEqual(datos['resumen']['pendientes'], 1)
                # La asistencia validada hoy entra en ambos periodos.
                self.assertEqual(datos['resumen']['horas_totales'], 4)

                self.assertEqual(len(datos['actividades']), 1)
                fila = datos['actividades'][0]
                self.assertEqual(
                    set(fila), {'nombre', 'estudiantes', 'horas', 'meta', 'pct'},
                )
                self.assertEqual(fila['nombre'], self.actividad.nombre_actividad)
                self.assertEqual(fila['horas'], 4)
                self.assertEqual(fila['meta'], 10)
                self.assertEqual(fila['pct'], 40)

    def test_un_tipo_invalido_responde_400(self):
        self._abrir_sesion()
        respuesta = self._reporte('anual')
        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(respuesta.json(), {'success': False, 'error': 'tipo invalido'})

    def test_preflight_options_del_dashboard_responde_204_con_cors(self):
        respuesta = self.client.options(
            reverse('api-dashboard-maestro'), HTTP_ORIGIN='http://localhost:3000',
        )
        self.assertEqual(respuesta.status_code, 204)
        self.assertEqual(
            respuesta['Access-Control-Allow-Origin'], 'http://localhost:3000',
        )


class ApiSesionServicioTests(BaseModuloDocentes):
    """
    Actividades que el docente registra en la tabla `sesionservicio`.

    El formulario de "Programar Sesiones de Taller" crea la fila con fecha,
    hora, duracion, estudiantes convocados y la evidencia subida; la accion
    posterior solo la marca Completada o Cancelada. Nadie toca filas ajenas.
    """

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.estudiante2 = Usuario.objects.create_user(
            correo='alumno2@test.local',
            password=CLAVE,
            nombre_completo='Segundo Alumno',
            codigo='EST-9998',
            rol=Usuario.ROL_ESTUDIANTE,
        )
        cls.otro_docente = Usuario.objects.create_user(
            correo='otro@test.local',
            password=CLAVE,
            nombre_completo='Otro Docente',
            codigo='DOC-8888',
            rol=Usuario.ROL_PROFESOR,
        )

    def setUp(self):
        # Las evidencias subidas en los tests no deben quedar en el repo.
        self.media = tempfile.mkdtemp(prefix='hs-media-')
        self.addCleanup(shutil.rmtree, self.media, True)
        self.ajuste_media = override_settings(MEDIA_ROOT=self.media)
        self.ajuste_media.enable()
        self.addCleanup(self.ajuste_media.disable)

    def _abrir_sesion(self):
        self.client.login(username=CORREO, password=CLAVE)

    def _lista(self, **extra):
        return self.client.get(reverse('api-sesionservicio-maestro'), **extra)

    def _accion(self, payload, **extra):
        return self.client.post(
            reverse('api-sesionservicio-accion'),
            data=json.dumps(payload),
            content_type='application/json',
            **extra,
        )

    def _registrar(self, **datos):
        payload = {
            'titulo': 'Seguridad en el taller',
            'taller': 'Taller 1',
            'fecha': (timezone.localdate() + timedelta(days=3)).isoformat(),
            'hora': '08:30',
            'duracion': '2 h',
            'nota': 'Llevar guantes',
            'estudiantes': [self.estudiante.pk, self.estudiante2.pk],
        }
        payload.update(datos)
        return self.client.post(reverse('api-sesionservicio-maestro'), data=payload)

    # ---------------------------------------------------------------- lista

    def test_la_lista_arranca_vacia_con_la_forma_esperada(self):
        self._abrir_sesion()
        respuesta = self._lista()
        self.assertEqual(respuesta.status_code, 200)
        datos = respuesta.json()

        self.assertTrue(datos['autenticado'])
        self.assertEqual(datos['docente']['nombre'], self.docente.nombre_completo)
        self.assertEqual(datos['tabla'], 'sesionservicio')
        self.assertEqual(
            datos['stats'], {'total': 0, 'programadas': 0, 'completadas': 0},
        )
        self.assertEqual(datos['registros'], [])

    # --------------------------------------------------------------- crear

    def test_registrar_una_actividad_guarda_la_fila_y_devuelve_201(self):
        self._abrir_sesion()
        respuesta = self._registrar()
        self.assertEqual(respuesta.status_code, 201)
        datos = respuesta.json()

        self.assertTrue(datos['success'])
        self.assertEqual(
            datos['stats'], {'total': 1, 'programadas': 1, 'completadas': 0},
        )

        fila = datos['registro']
        self.assertEqual(
            set(fila),
            {
                'id', 'titulo', 'nota', 'taller', 'fecha', 'hora', 'duracion',
                'estado', 'evidencia', 'evidencia_url', 'subida', 'estudiantes',
            },
        )
        self.assertEqual(fila['titulo'], 'Seguridad en el taller')
        self.assertEqual(fila['taller'], 'Taller 1')
        self.assertEqual(fila['hora'], '08:30')
        self.assertEqual(fila['duracion'], '2 h')
        self.assertEqual(fila['estado'], SesionServicio.ESTADO_PROGRAMADA)
        self.assertEqual(fila['evidencia'], '')
        self.assertEqual(fila['nota'], 'Llevar guantes')

        # La fila existe de verdad en la tabla y quedo a nombre del docente.
        registro = SesionServicio.objects.get(pk=fila['id'])
        self.assertEqual(registro.id_docente_id, self.docente.pk)
        self.assertEqual(registro.descripcion, 'Llevar guantes')

        # Y convoco a los dos estudiantes elegidos, con sus iniciales.
        convocados = sorted(e.codigo for e in registro.estudiantes.all())
        self.assertEqual(convocados, sorted([self.estudiante.codigo, 'EST-9998']))
        self.assertEqual(
            {e['iniciales'] for e in fila['estudiantes']}, {'AD', 'SA'},
        )

    def test_registrar_con_evidencia_guarda_el_archivo(self):
        self._abrir_sesion()
        evidencia = SimpleUploadedFile(
            'planilla.txt', b'lista de asistencia', content_type='text/plain',
        )
        respuesta = self._registrar(evidencia=evidencia)
        self.assertEqual(respuesta.status_code, 201)

        fila = respuesta.json()['registro']
        self.assertTrue(fila['evidencia'].endswith('planilla.txt'))
        self.assertIn('/media/evidencias/', fila['evidencia_url'])

        registro = SesionServicio.objects.get(pk=fila['id'])
        with open(registro.evidencia.path, 'rb') as archivo:
            self.assertEqual(archivo.read(), b'lista de asistencia')

    def test_registrar_por_json_tambien_funciona(self):
        self._abrir_sesion()
        respuesta = self.client.post(
            reverse('api-sesionservicio-maestro'),
            data=json.dumps({
                'titulo': 'Manejo de herramientas',
                'fecha': timezone.localdate().isoformat(),
                'hora': '10:00',
                'duracion': '3 h',
                'estudiantes': [self.estudiante.pk],
            }),
            content_type='application/json',
        )
        self.assertEqual(respuesta.status_code, 201)
        self.assertEqual(respuesta.json()['registro']['taller'], 'Bodega general')

    def test_solo_los_estudiantes_quedan_convocados(self):
        self._abrir_sesion()
        respuesta = self._registrar(
            estudiantes=[self.estudiante.pk, self.otro_docente.pk],
        )
        self.assertEqual(respuesta.status_code, 201)

        registro = SesionServicio.objects.get(pk=respuesta.json()['registro']['id'])
        self.assertEqual(
            [e.pk for e in registro.estudiantes.all()], [self.estudiante.pk],
        )

    def test_las_actividades_mas_nuevas_van_primero(self):
        self._abrir_sesion()
        hoy = timezone.localdate()
        self._registrar(titulo='Vieja', fecha=(hoy + timedelta(days=1)).isoformat(), hora='07:00')
        self._registrar(titulo='Nueva', fecha=(hoy + timedelta(days=5)).isoformat(), hora='09:00')

        titulos = [f['titulo'] for f in self._lista().json()['registros']]
        self.assertEqual(titulos, ['Nueva', 'Vieja'])

    def test_datos_invalidos_responden_400(self):
        self._abrir_sesion()
        casos = {
            'sin titulo': {'titulo': '   '},
            'sin fecha': {'fecha': ''},
            'fecha mal formada': {'fecha': '3 de octubre'},
            'sin hora': {'hora': ''},
            'hora mal formada': {'hora': '8:30 de la mañana'},
            'duracion invalida': {'duracion': '5 h'},
        }
        for nombre, cambio in casos.items():
            with self.subTest(caso=nombre):
                respuesta = self._registrar(**cambio)
                self.assertEqual(respuesta.status_code, 400)
                self.assertFalse(respuesta.json()['success'])
        self.assertFalse(SesionServicio.objects.exists())

    def test_un_json_invalido_responde_400(self):
        self._abrir_sesion()
        respuesta = self.client.post(
            reverse('api-sesionservicio-maestro'),
            data='{no es json',
            content_type='application/json',
        )
        self.assertEqual(respuesta.status_code, 400)
        self.assertFalse(respuesta.json()['success'])

    # -------------------------------------------------------------- accion

    def test_completar_y_cancelar_cambian_el_estado(self):
        self._abrir_sesion()
        primero = self._registrar(titulo='Soldadura').json()['registro']['id']
        segundo = self._registrar(titulo='Electricidad').json()['registro']['id']

        respuesta = self._accion({'id_registro': primero, 'accion': 'completar'})
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(
            respuesta.json()['registro']['estado'], SesionServicio.ESTADO_COMPLETADA,
        )
        self.assertEqual(
            respuesta.json()['stats'], {'total': 2, 'programadas': 1, 'completadas': 1},
        )
        self.assertEqual(
            SesionServicio.objects.get(pk=primero).estado,
            SesionServicio.ESTADO_COMPLETADA,
        )

        respuesta = self._accion({'id_registro': segundo, 'accion': 'cancelar'})
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(
            respuesta.json()['registro']['estado'], SesionServicio.ESTADO_CANCELADA,
        )

    def test_marcar_la_actividad_de_otro_docente_responde_403(self):
        self._abrir_sesion()
        ajena = SesionServicio.objects.create(
            id_docente=self.otro_docente,
            titulo='Actividad ajena',
            taller='Taller 9',
            fecha=timezone.localdate(),
            hora=time(9, 0),
        )

        respuesta = self._accion({'id_registro': ajena.pk, 'accion': 'completar'})
        self.assertEqual(respuesta.status_code, 403)
        ajena.refresh_from_db()
        self.assertEqual(ajena.estado, SesionServicio.ESTADO_PROGRAMADA)

    def test_una_accion_o_un_registro_invalido_no_tocan_nada(self):
        self._abrir_sesion()
        registro = self._registrar().json()['registro']['id']

        casos = [
            ({'id_registro': registro, 'accion': 'borrar'}, 400),
            ({'accion': 'completar'}, 400),
            ({'id_registro': 999999, 'accion': 'completar'}, 404),
        ]
        for payload, esperado in casos:
            with self.subTest(payload=payload):
                self.assertEqual(self._accion(payload).status_code, esperado)

        self.assertEqual(
            SesionServicio.objects.get(pk=registro).estado,
            SesionServicio.ESTADO_PROGRAMADA,
        )

    def test_el_preflight_responde_204_con_cors(self):
        respuesta = self.client.options(
            reverse('api-sesionservicio-maestro'), HTTP_ORIGIN='http://localhost:3000',
        )
        self.assertEqual(respuesta.status_code, 204)
        self.assertEqual(
            respuesta['Access-Control-Allow-Origin'], 'http://localhost:3000',
        )

    def test_cada_docente_solo_ve_sus_propias_actividades(self):
        self._abrir_sesion()
        self._registrar(titulo='Mia')
        SesionServicio.objects.create(
            id_docente=self.otro_docente,
            titulo='De otro',
            taller='Taller 9',
            fecha=timezone.localdate(),
            hora=time(9, 0),
        )

        titulos = [f['titulo'] for f in self._lista().json()['registros']]
        self.assertEqual(titulos, ['Mia'])
