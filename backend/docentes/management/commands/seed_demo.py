"""
Comando de gestion: crea datos de prueba del modulo de Docentes.

Uso:
    python manage.py seed_demo

Es idempotente: se puede ejecutar varias veces sin duplicar registros.
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from docentes.models import Actividad, Asistencia, Sesion, Usuario

CLAVE_DOCENTE = 'Docente2026*'
CLAVE_DIRECTIVO = 'Directivo2026*'
CLAVE_ESTUDIANTE = 'Estudiante2026*'

CORREO_DOCENTE = 'docente@horasocial.local'
CORREO_DIRECTIVO = 'director@horasocial.local'


class Command(BaseCommand):
    help = 'Crea datos de prueba para el modulo de Docentes (idempotente).'

    def log(self, mensaje):
        self.stdout.write(f'  {mensaje}')

    def obtener_o_crear_usuario(self, correo, clave, **valores):
        """
        Crea el usuario si no existe y garantiza que tenga contrasena usable.

        Si el usuario ya existe pero quedo sin contrasena (por ejemplo creado
        a mano desde SQL), se le asigna la clave de prueba.
        """
        usuario, creado = Usuario.objects.get_or_create(correo=correo, defaults=valores)
        if creado or not usuario.has_usable_password():
            usuario.set_password(clave)
            usuario.save()
        return usuario, creado

    def handle(self, *args, **options):
        # --------------------------- Directivo ---------------------------
        directivo, creado = self.obtener_o_crear_usuario(
            CORREO_DIRECTIVO,
            CLAVE_DIRECTIVO,
            nombre_completo='Direccion Academica',
            rol=Usuario.ROL_DIRECTIVO,
            estado_cuenta=Usuario.ESTADO_ACTIVO,
            is_staff=True,
            is_superuser=True,
        )
        self.log(f'Directivo {"creado" if creado else "existente"}: {directivo.correo}')

        # ---------------------------- Docente ----------------------------
        docente, creado = self.obtener_o_crear_usuario(
            CORREO_DOCENTE,
            CLAVE_DOCENTE,
            nombre_completo='Carlos Andres Mejia',
            codigo='DOC-0001',
            rol=Usuario.ROL_PROFESOR,
            grado='Tecnico',
            estado_cuenta=Usuario.ESTADO_ACTIVO,
        )
        self.log(f'Docente {"creado" if creado else "existente"}: {docente.correo}')

        # -------------------------- Estudiantes --------------------------
        datos_estudiantes = [
            ('Ana Maria Torres', 'EST-0001', '10-A'),
            ('Juan David Rojas', 'EST-0002', '10-A'),
            ('Laura Sofia Herrera', 'EST-0003', '11-B'),
        ]
        estudiantes = []
        for indice, (nombre, codigo, grado) in enumerate(datos_estudiantes, start=1):
            estudiante, creado = self.obtener_o_crear_usuario(
                f'estudiante{indice}@horasocial.local',
                CLAVE_ESTUDIANTE,
                nombre_completo=nombre,
                codigo=codigo,
                grado=grado,
                rol=Usuario.ROL_ESTUDIANTE,
                estado_cuenta=Usuario.ESTADO_ACTIVO,
            )
            estudiantes.append(estudiante)
            self.log(f'Estudiante {"creado" if creado else "existente"}: {codigo} {nombre}')

        # ---------------------------- Actividad --------------------------
        actividad, creada = Actividad.objects.get_or_create(
            nombre_actividad='Refuerzo escolar comunitario',
            defaults={
                'categoria': Actividad.CATEGORIA_GENERAL,
                'descripcion': 'Apoyo academico a estudiantes de primaria.',
            },
        )
        self.log(f'Actividad {"creada" if creada else "existente"}: {actividad.nombre_actividad}')

        # ----------------------------- Brigada ---------------------------
        sesion, creada = Sesion.objects.get_or_create(
            id_profesor=docente,
            id_tipo=actividad,
            defaults={
                'fecha_hora': timezone.now() + timedelta(days=3),
                'ubicacion': 'Biblioteca municipal',
                'cupos_max': 20,
                'cupos_disponibles': 20,
                'estado': Sesion.ESTADO_PROGRAMADA,
            },
        )
        self.log(f'Brigada {"creada" if creada else "existente"}: #{sesion.id_sesion}')

        # --------------------------- Asistencia --------------------------
        for estudiante in estudiantes:
            asistencia, creada = Asistencia.objects.get_or_create(
                id_sesion=sesion,
                id_estudiante=estudiante,
                defaults={
                    'confirmacion': Asistencia.CONFIRMACION_ASISTE,
                    'validacion_prof': Asistencia.VALIDACION_CUMPLIDA,
                    'horas_ganadas': 4,
                    'fecha_confirmacion': timezone.now(),
                },
            )
            self.log(
                f'Asistencia {"creada" if creada else "existente"}: '
                f'{estudiante.codigo} -> {asistencia.horas_ganadas} horas'
            )

        # ----------------------------- Resumen ---------------------------
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('Datos de prueba listos. Credenciales:'))
        self.stdout.write(f'  Directivo   -> {CORREO_DIRECTIVO} / {CLAVE_DIRECTIVO}  (para /admin/)')
        self.stdout.write(f'  Docente     -> {CORREO_DOCENTE} / {CLAVE_DOCENTE}')
        self.stdout.write(f'  Estudiante  -> estudiante1@horasocial.local / {CLAVE_ESTUDIANTE}')
