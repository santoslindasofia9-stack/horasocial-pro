"""
Comando de gestion: siembra datos reales para el panel del docente.

Uso:
    python manage.py sembrar_datos_dashboard

Con `--limpiar` borra primero las asistencias de las sesiones del docente,
util para dejar el panel en el juego exacto de la demostracion (10
estudiantes). No toca usuarios ni actividades.

Es idempotente. Las claves naturales son:
    - usuario  -> codigo academico
    - actividad -> nombre_actividad
    - sesion    -> (docente, actividad, fecha_hora)
    - asistencia -> (sesion, estudiante)
    - mensaje   -> (docente, estudiante, remitente, contenido)

Las fechas de las sesiones se anclan a la fecha de ejecucion con horas
fijas (-18/-15/-12 dias realizadas, +7/+14/+21 dias programadas), de modo
que una segunda corrida el mismo dia calcula exactamente las mismas fechas
y reutiliza todo lo ya creado. Una segunda corrida reporta 0 creados.

Los mensajes del chat tambien se anclan a la hora de ejecucion (minutos
atras), asi que la bandeja siempre se ve con movimiento reciente.
"""

from datetime import datetime, time, timedelta

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.utils import timezone

from docentes.models import Actividad, Asistencia, Mensaje, Sesion, Usuario

CODIGO_DOCENTE = 'sofia'
CLAVE_ESTUDIANTE = 'Estudiante2026*'

# (codigo, nombre, grado) - 10 estudiantes, grado alternado 10-A / 11-B.
ESTUDIANTES = [
    ('EST-D01', 'Camilo Andres Vera', '10-A'),
    ('EST-D02', 'Valentina Rojas', '11-B'),
    ('EST-D03', 'Santiago Herrera', '10-A'),
    ('EST-D04', 'Daniela Castro', '11-B'),
    ('EST-D05', 'Mateo Gutierrez', '10-A'),
    ('EST-D06', 'Isabella Moreno', '11-B'),
    ('EST-D07', 'Nicolas Romero', '10-A'),
    ('EST-D08', 'Gabriela Fuentes', '11-B'),
    ('EST-D09', 'Sebastian Ortiz', '10-A'),
    ('EST-D10', 'Laura Jimenez', '11-B'),
]

# (nombre, categoria, descripcion)
ACTIVIDADES = [
    (
        'Refuerzo escolar comunitario',
        Actividad.CATEGORIA_GENERAL,
        'Apoyo academico en brigadas de refuerzo para la comunidad.',
    ),
    (
        'Jardin botanico escolar',
        Actividad.CATEGORIA_GENERAL,
        'Cuidado del jardin y la huerta del plantel.',
    ),
    (
        'Tutoria entre pares',
        Actividad.CATEGORIA_ESPECIFICA,
        'Estudiantes de mayor grado acompanan a sus pares.',
    ),
]

# (indice de actividad, dias respecto a hoy, hora, ubicacion, cupos, estado)
SESIONES = [
    (0, -18, 9, 'Biblioteca municipal', 22, Sesion.ESTADO_REALIZADA),
    (1, -15, 14, 'Huerta escolar', 20, Sesion.ESTADO_REALIZADA),
    (2, -12, 9, 'Salon 3 - bloque B', 24, Sesion.ESTADO_REALIZADA),
    (0, 7, 9, 'Biblioteca municipal', 22, Sesion.ESTADO_PROGRAMADA),
    (1, 14, 14, 'Parque central', 20, Sesion.ESTADO_PROGRAMADA),
    (2, 21, 10, 'Aula de medios', 24, Sesion.ESTADO_PROGRAMADA),
]

# (indice de sesion, codigos, validacion, confirmacion, horas)
ASISTENCIAS = [
    (0, ['EST-D01', 'EST-D02', 'EST-D03'],
     Asistencia.VALIDACION_CUMPLIDA, Asistencia.CONFIRMACION_ASISTE, 4),
    (1, ['EST-D04'],
     Asistencia.VALIDACION_CUMPLIDA, Asistencia.CONFIRMACION_ASISTE, 4),
    (1, ['EST-D05'],
     Asistencia.VALIDACION_INASISTENCIA, Asistencia.CONFIRMACION_NO_ASISTE, 0),
    (2, ['EST-D06'],
     Asistencia.VALIDACION_CUMPLIDA, Asistencia.CONFIRMACION_ASISTE, 4),
    (2, ['EST-D07'],
     Asistencia.VALIDACION_INASISTENCIA, Asistencia.CONFIRMACION_NO_ASISTE, 0),
    (3, ['EST-D08', 'EST-D09', 'EST-D10'],
     Asistencia.VALIDACION_POR_VALIDAR, Asistencia.CONFIRMACION_ASISTE, 4),
    (4, ['EST-D08', 'EST-D09'],
     Asistencia.VALIDACION_POR_VALIDAR, Asistencia.CONFIRMACION_ASISTE, 4),
                creados['asistencias'] += 1
            else:
                reuse['asistencias'] += 1

        # ----------------------------- Mensajes ----------------------------
        ahora = timezone.now()
        for codigo, remitente, contenido, minutos, leido, con_adjunto in MENSAJES:
            mensaje, creado = Mensaje.objects.get_or_create(
                id_docente=docente,
                id_estudiante=por_codigo[codigo],
                remitente=remitente,
                contenido=contenido,
            )
            if creado:
                cambios = {
                    'fecha_hora': ahora - timedelta(minutes=minutos),
                    'estado': (Mensaje.ESTADO_LEIDO if leido
                               else Mensaje.ESTADO_ENVIADO),
                }
                if con_adjunto:
                    # El adjunto se guarda en MEDIA y la fila apunta a el.
                    mensaje.adjunto.save(
                        'plan-de-mejora.txt',
                        ContentFile(PLAN_DE_MEJORA.encode('utf-8')),
                        save=False,
                    )
                    mensaje.adjunto_nombre = 'plan-de-mejora.txt'
                    mensaje.adjunto_tipo = Mensaje.ADJUNTO_ARCHIVO
                    cambios['adjunto'] = mensaje.adjunto.name
                    cambios['adjunto_nombre'] = mensaje.adjunto_nombre
                    cambios['adjunto_tipo'] = mensaje.adjunto_tipo
                # `fecha_hora` es auto_now_add, asi que el momento real de la
                # conversacion se fija con un update posterior al insert.
                Mensaje.objects.filter(pk=mensaje.pk).update(**cambios)
                creados['mensajes'] += 1
            else:
                reuse['mensajes'] += 1

        # Conexion de los estudiantes que la demo muestra en linea.
        Usuario.objects.filter(
            pk__in=[por_codigo[codigo].pk for codigo in EN_LINEA],
        ).update(last_login=timezone.now() - timedelta(minutes=MINUTOS_EN_LINEA))

# Documento que acompana uno de los mensajes sembrados.
PLAN_DE_MEJORA = """PLAN DE MEJORA - SERVICIO SOCIAL
Estudiante: Daniela Castro (EST-D04)
Grado: 11-B

1. Asistir puntualmente a las sesiones programadas.
2. Entregar el registro fotografico de cada jornada.
3. Completar las horas pendientes antes del cierre del periodo.

Observacion del docente: se aprueba el plan y se hace seguimiento
semanal durante las brigadas de refuerzo escolar.
"""

# Conversacion sembrada: (codigo, remitente, texto, minutos atras, leido, adjunto)
# `leido` es el estado que ve la bandeja: los mensajes del estudiante sin leer
# alimentan el contador de no leidos.
DOCENTE = Mensaje.REMITENTE_DOCENTE
ESTUDIANTE = Mensaje.REMITENTE_ESTUDIANTE

MENSAJES = [
    ('EST-D01', ESTUDIANTE, 'Profe, la charla de seguridad es en la biblioteca?',
     240, True, False),
    ('EST-D01', DOCENTE, 'Si, Camilo. Nos vemos a las 9:30 en la biblioteca municipal.',
     225, True, False),
    ('EST-D01', ESTUDIANTE, 'Perfecto, profe. Llevo el cuaderno de campo.',
     35, False, False),
    ('EST-D04', DOCENTE, 'Daniela, revisa el plan de mejora antes del viernes.',
     310, True, False),
    ('EST-D04', ESTUDIANTE, 'Le adjunto el plan de mejora corregido, profe.',
     145, False, True),
    ('EST-D08', DOCENTE, 'Gabriela, felicitaciones por la asistencia a la jornada.',
     1560, True, False),
]

# Estudiantes con sesion abierta: su `last_login` queda a minutos de la
# corrida y el punto verde de la bandeja es un dato real, no un adorno.
EN_LINEA = ['EST-D01', 'EST-D04', 'EST-D08']
MINUTOS_EN_LINEA = 4


class Command(BaseCommand):
    help = (
        'Siembra estudiantes, actividades, sesiones y asistencias del panel '
        'del docente (idempotente).'
    )

    def log(self, mensaje):
        self.stdout.write(f'  {mensaje}')

    def add_arguments(self, parser):
        parser.add_argument(
            '--limpiar',
            action='store_true',
            help=(
                'Borra las asistencias de las sesiones de este docente antes de '
                'sembrar. Sirve para dejar el panel en el juego de datos exacto '
                'de la demostracion (no toca usuarios ni actividades).'
            ),
        )

    def handle(self, *args, **options):
        docente = Usuario.objects.filter(codigo=CODIGO_DOCENTE).first()
        if docente is None:
            self.stderr.write(self.style.ERROR(
                f'No existe el docente con codigo "{CODIGO_DOCENTE}". '
                'Crealo antes de sembrar los datos del panel.',
            ))
            return

        if options.get('limpiar'):
            borradas, _ = Asistencia.objects.filter(
                id_sesion__id_profesor=docente,
            ).delete()
            self.stdout.write('')
            self.log(f'Limpiar      : {borradas} asistencias borradas')

        creados = {'estudiantes': 0, 'actividades': 0, 'sesiones': 0,
                   'asistencias': 0, 'mensajes': 0}
        reuse = {'estudiantes': 0, 'actividades': 0, 'sesiones': 0,
                 'asistencias': 0, 'mensajes': 0}

        # --------------------------- Estudiantes ---------------------------
        por_codigo = {}
        for codigo, nombre, grado in ESTUDIANTES:
            estudiante, creado = Usuario.objects.get_or_create(
                codigo=codigo,
                defaults={
                    'nombre_completo': nombre,
                    'correo': f'{codigo.lower().replace("-", "")}@horasocial.local',
                    'rol': Usuario.ROL_ESTUDIANTE,
                    'grado': grado,
                    'estado_cuenta': Usuario.ESTADO_ACTIVO,
                },
            )
            if creado:
                # Solo al crear: una segunda corrida no toca la clave ya
                # cifrada ni el perfil del estudiante.
                estudiante.set_password(CLAVE_ESTUDIANTE)
                estudiante.save(update_fields=['password'])
                creados['estudiantes'] += 1
            else:
                reuse['estudiantes'] += 1
            por_codigo[codigo] = estudiante

        # --------------------------- Actividades ---------------------------
        por_nombre = {}
        for nombre, categoria, descripcion in ACTIVIDADES:
            actividad, creada = Actividad.objects.get_or_create(
                nombre_actividad=nombre,
                defaults={'categoria': categoria, 'descripcion': descripcion},
            )
            if creada:
                creados['actividades'] += 1
            else:
                reuse['actividades'] += 1
            por_nombre[nombre] = actividad

        # ----------------------------- Sesiones ----------------------------
        # Fecha anclada a HOY con hora fija: dos corridas el mismo dia
        # calculan la misma fecha_hora y el get_or_create reutiliza.
        hoy = timezone.localdate()

        def fecha(dias, hora):
            naive = datetime.combine(hoy + timedelta(days=dias), time(hora))
            return timezone.make_aware(naive)

        sesiones = []
        for indice_actividad, dias, hora, ubicacion, cupos, estado in SESIONES:
            actividad = por_nombre[ACTIVIDADES[indice_actividad][0]]
            sesion, creada = Sesion.objects.get_or_create(
                id_profesor=docente,
                id_tipo=actividad,
                fecha_hora=fecha(dias, hora),
                defaults={
                    'ubicacion': ubicacion,
                    'cupos_max': cupos,
                    'cupos_disponibles': cupos,
                    'estado': estado,
                },
            )
            if creada:
                creados['sesiones'] += 1
            else:
                reuse['sesiones'] += 1
            sesiones.append(sesion)

        # --------------------------- Asistencias ---------------------------
        for indice_sesion, codigos, validacion, confirmacion, horas in ASISTENCIAS:
            sesion = sesiones[indice_sesion]
            for codigo in codigos:
                asistencia, creada = Asistencia.objects.get_or_create(
                    id_sesion=sesion,
                    id_estudiante=por_codigo[codigo],
                    defaults={
                        'confirmacion': confirmacion,
                        'validacion_prof': validacion,
                        'horas_ganadas': horas,
                        'fecha_confirmacion': timezone.now(),
                    },
                )
                if creada:
                    creados['asistencias'] += 1
                else:
                    reuse['asistencias'] += 1

        # Los cupos libres reflejan lo realmente ocupado en cada sesion.
        for sesion in sesiones:
            ocupados = sesion.asistencias.count()
            disponibles = max(sesion.cupos_max - ocupados, 0)
            if sesion.cupos_disponibles != disponibles:
                sesion.cupos_disponibles = disponibles
                sesion.save(update_fields=['cupos_disponibles'])

        # ------------------------------ Resumen ----------------------------
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'Siembra del panel de {docente.nombre_completo} ({CODIGO_DOCENTE}):'
        ))
        self.stdout.write('')
        for clave in ('estudiantes', 'actividades', 'sesiones', 'asistencias'):
            self.log(
                f'{clave.capitalize():<13}: {creados[clave]} creados, '
                f'{reuse[clave]} ya existentes'
            )

        totales = (
            Asistencia.objects.filter(id_sesion__id_profesor=docente)
            .values_list('validacion_prof', flat=True)
        )
        conteo = {estado: 0 for estado, _ in Asistencia.VALIDACION_CHOICES}
        for estado in totales:
            conteo[estado] = conteo.get(estado, 0) + 1

        self.stdout.write('')
        self.log(
            f'Totales      : {len(ESTUDIANTES)} estudiantes, '
            f'{len(ACTIVIDADES)} actividades, {len(sesiones)} sesiones, '
            f'{sum(conteo.values())} asistencias'
        )
        self.log(f"Por Validar  : {conteo[Asistencia.VALIDACION_POR_VALIDAR]}")
        self.log(f"Cumplida     : {conteo[Asistencia.VALIDACION_CUMPLIDA]}")
        self.log(f"Inasistencia : {conteo[Asistencia.VALIDACION_INASISTENCIA]}")

        total_creados = sum(creados.values())
        self.stdout.write('')
        if total_creados == 0:
            self.stdout.write(self.style.SUCCESS(
                'Nada que crear: los datos ya existian (0 creados en esta corrida).'
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'{total_creados} registros creados en esta corrida.'
            ))
        self.stdout.write(
            'Nota: las fechas de las sesiones se anclan al dia de ejecucion, '
            'asi que una segunda corrida el mismo dia no duplica nada.'
        )
