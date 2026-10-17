"""Pruebas del modulo de Docentes.

Se ejecutan con:
    python manage.py test docentes

Usan una base de datos de prueba aparte, asi que no tocan los datos reales.
"""

from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Actividad, Asistencia, Sesion, Usuario

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
