"""
Modelos del modulo de Docentes - HORASOCIAL PRO.

Esquema replicado del diseno original (tablas `usuariosa`, `cronograma_sesiones`,
`asistencia_detalle`, `actividades_maestrasa`, `lista_esperaa`,
`solicitudes_recuperacion_maestros`).

Decisiones de diseno relevantes:

1. `Usuario` extiende AbstractBaseUser + PermissionsMixin en lugar de guardar la
   contrasena en un CharField propio. Django aplica hashing PBKDF2-SHA256 con
   salt, agrega gestion de sesiones y permisos, y nunca guarda texto plano.
2. El login es por CORREO electronico (USERNAME_FIELD = 'correo').
3. El campo `codigo` se agrego al diseno original para el identificador
   academico del estudiante (requisito del modulo).
"""

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.db.models import Sum
from django.utils import timezone


# ==========================================================================
# GESTOR DE USUARIOS
# ==========================================================================

class UsuarioManager(BaseUserManager):
    """Gestor que crea usuarios con contrasena cifrada."""

    use_in_migrations = True

    def _crear(self, correo, password, **extra):
        if not correo:
            raise ValueError('El correo electronico es obligatorio.')
        correo = self.normalize_email(correo).lower().strip()
        usuario = self.model(correo=correo, **extra)
        # set_password() aplica el hasher configurado (PBKDF2 por defecto).
        usuario.set_password(password)
        usuario.save(using=self._db)
        return usuario

    def create_user(self, correo, password=None, **extra):
        extra.setdefault('rol', Usuario.ROL_ESTUDIANTE)
        extra.setdefault('estado_cuenta', Usuario.ESTADO_ACTIVO)
        return self._crear(correo, password, **extra)

    def create_superuser(self, correo, password=None, **extra):
        extra.setdefault('rol', Usuario.ROL_DIRECTIVO)
        extra.setdefault('estado_cuenta', Usuario.ESTADO_ACTIVO)
        extra.setdefault('is_staff', True)
        extra.setdefault('is_superuser', True)

        if extra.get('is_staff') is not True:
            raise ValueError('El superusuario debe tener is_staff=True.')
        if extra.get('is_superuser') is not True:
            raise ValueError('El superusuario debe tener is_superuser=True.')

        return self._crear(correo, password, **extra)


# ==========================================================================
# USUARIO (tabla: usuariosa)
# ==========================================================================

class Usuario(AbstractBaseUser, PermissionsMixin):
    """
    Usuario unico del sistema: docentes, estudiantes y directivos.

    La contrasena se almacena cifrada por Django (columna `password`,
    varchar(255) con el hash). Nunca se guarda en texto plano.
    """

    ROL_ESTUDIANTE = 'Estudiante'
    ROL_PROFESOR = 'Profesor'
    ROL_DIRECTIVO = 'Directivo'
    ROL_CHOICES = [
        (ROL_ESTUDIANTE, 'Estudiante'),
        (ROL_PROFESOR, 'Profesor'),
        (ROL_DIRECTIVO, 'Directivo'),
    ]

    ESTADO_ACTIVO = 'Activo'
    ESTADO_BLOQUEADO = 'Bloqueado'
    ESTADO_INACTIVO = 'Inactivo'
    ESTADO_CHOICES = [
        (ESTADO_ACTIVO, 'Activo'),
        (ESTADO_BLOQUEADO, 'Bloqueado'),
        (ESTADO_INACTIVO, 'Inactivo'),
    ]

    id_usuario = models.AutoField(primary_key=True)
    nombre_completo = models.CharField('nombre completo', max_length=150)
    correo = models.EmailField('correo electronico', max_length=100, unique=True)
    codigo = models.CharField(
        'codigo academico', max_length=20, unique=True, null=True, blank=True,
        help_text='Identificador del estudiante (ej. EST-0001).',
    )
    rol = models.CharField(max_length=20, choices=ROL_CHOICES, default=ROL_ESTUDIANTE)
    grado = models.CharField(max_length=20, null=True, blank=True)
    intentos_fallidos = models.PositiveIntegerField(default=0)
    estado_cuenta = models.CharField(
        max_length=20, choices=ESTADO_CHOICES, default=ESTADO_ACTIVO,
    )

    # Campos requeridos por Django.
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UsuarioManager()

    USERNAME_FIELD = 'correo'
    REQUIRED_FIELDS = ['nombre_completo']

    class Meta:
        db_table = 'usuariosa'
        verbose_name = 'Usuario'
        verbose_name_plural = 'Usuarios'
        ordering = ['nombre_completo']

    def __str__(self):
        return f'{self.nombre_completo} ({self.correo})'

    def save(self, *args, **kwargs):
        # El correo siempre en minusculas: evita duplicados tipo Ana@x / ana@x.
        if self.correo:
            self.correo = self.correo.lower().strip()
        super().save(*args, **kwargs)

    # ----------------------------- Propiedades -----------------------------

    @property
    def es_docente(self):
        return self.rol == self.ROL_PROFESOR

    @property
    def es_estudiante(self):
        return self.rol == self.ROL_ESTUDIANTE

    @property
    def tiene_acceso(self):
        """Puede iniciar sesion? (cuenta activa y no bloqueada)."""
        return self.estado_cuenta == self.ESTADO_ACTIVO and self.is_active

    # ------------------------ Control de intentos --------------------------

    def registrar_intento_fallido(self, maximo=5):
        """Suma un intento fallido y bloquea la cuenta al alcanzar el maximo."""
        self.intentos_fallidos += 1
        if self.intentos_fallidos >= maximo:
            self.estado_cuenta = self.ESTADO_BLOQUEADO
        self.save(update_fields=['intentos_fallidos', 'estado_cuenta'])

    def reiniciar_intentos(self):
        """Limpia los intentos fallidos tras un login correcto."""
        if self.intentos_fallidos or self.estado_cuenta == self.ESTADO_BLOQUEADO:
            self.intentos_fallidos = 0
            if self.estado_cuenta == self.ESTADO_BLOQUEADO:
                self.estado_cuenta = self.ESTADO_ACTIVO
            self.save(update_fields=['intentos_fallidos', 'estado_cuenta'])


# ==========================================================================
# PROXIES: DOCENTE y ESTUDIANTE
# ==========================================================================

class DocenteManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(rol=Usuario.ROL_PROFESOR)


class EstudianteManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(rol=Usuario.ROL_ESTUDIANTE)


class Docente(Usuario):
    """
    Vista tipada de Usuario para el rol Profesor.

    `Docente.objects.all()` ya filtra por rol, y expone las relaciones del
    modulo: brigadas asignadas, estudiantes a cargo y horas validadas.
    """

    objects = DocenteManager()

    class Meta:
        proxy = True
        verbose_name = 'Docente'
        verbose_name_plural = 'Docentes'

    @property
    def brigadas_asignadas(self):
        """Sesiones/cronogramas que este docente tiene asignados."""
        return self.sesiones_dirigidas.select_related('id_tipo').all()

    @property
    def estudiantes_a_cargo(self):
        """Estudiantes que asisten a alguna sesion de este docente."""
        return Estudiante.objects.filter(
            asistencias__id_sesion__id_profesor=self,
        ).distinct()

    def total_horas_validadas(self):
        """Suma de horas con validacion 'Cumplida' en sus sesiones."""
        total = Asistencia.objects.filter(
            id_sesion__id_profesor=self,
            validacion_prof=Asistencia.VALIDACION_CUMPLIDA,
        ).aggregate(total=Sum('horas_ganadas'))
        return total['total'] or 0

    def resumen(self):
        return {
            'brigadas': self.brigadas_asignadas.count(),
            'estudiantes': self.estudiantes_a_cargo.count(),
            'horas_validadas': self.total_horas_validadas(),
        }


class Estudiante(Usuario):
    """Vista tipada de Usuario para el rol Estudiante."""

    objects = EstudianteManager()

    class Meta:
        proxy = True
        verbose_name = 'Estudiante'
        verbose_name_plural = 'Estudiantes'

    @property
    def horas_registradas(self):
        """Horas ganadas y validadas por el docente."""
        total = self.asistencias.filter(
            validacion_prof=Asistencia.VALIDACION_CUMPLIDA,
        ).aggregate(total=Sum('horas_ganadas'))
        return total['total'] or 0

    @property
    def horas_pendientes(self):
        """Horas confirmadas pero aun sin validar."""
        total = self.asistencias.filter(
            validacion_prof=Asistencia.VALIDACION_POR_VALIDAR,
        ).aggregate(total=Sum('horas_ganadas'))
        return total['total'] or 0


# ==========================================================================
# ACTIVIDAD (tabla: actividades_maestrasa)
# ==========================================================================

class Actividad(models.Model):
    """Tipo de actividad de horas sociales (institucional o especifica)."""

    CATEGORIA_GENERAL = 'Institucion General'
    CATEGORIA_ESPECIFICA = 'Institucion Especifico'
    CATEGORIA_CHOICES = [
        (CATEGORIA_GENERAL, 'Institucion General'),
        (CATEGORIA_ESPECIFICA, 'Institucion Especifico'),
    ]

    id_tipo = models.AutoField(primary_key=True)
    categoria = models.CharField(max_length=40, choices=CATEGORIA_CHOICES)
    nombre_actividad = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'actividades_maestrasa'
        verbose_name = 'Actividad'
        verbose_name_plural = 'Actividades'
        ordering = ['nombre_actividad']

    def __str__(self):
        return self.nombre_actividad


# ==========================================================================
# SESION / BRIGADA (tabla: cronograma_sesiones)
# ==========================================================================

class Sesion(models.Model):
    """Sesion programada: la brigada asignada a un docente."""

    ESTADO_PROGRAMADA = 'Programada'
    ESTADO_REALIZADA = 'Realizada'
    ESTADO_CANCELADA = 'Cancelada'
    ESTADO_CHOICES = [
        (ESTADO_PROGRAMADA, 'Programada'),
        (ESTADO_REALIZADA, 'Realizada'),
        (ESTADO_CANCELADA, 'Cancelada'),
    ]

    id_sesion = models.AutoField(primary_key=True)
    id_profesor = models.ForeignKey(
        Usuario, on_delete=models.PROTECT, db_column='id_profesor',
        related_name='sesiones_dirigidas',
        limit_choices_to={'rol': Usuario.ROL_PROFESOR},
        verbose_name='docente',
    )
    id_tipo = models.ForeignKey(
        Actividad, on_delete=models.PROTECT, db_column='id_tipo',
        related_name='sesiones', verbose_name='actividad',
    )
    fecha_hora = models.DateTimeField()
    ubicacion = models.CharField(max_length=100)
    cupos_max = models.PositiveIntegerField(default=0)
    cupos_disponibles = models.PositiveIntegerField(default=0)
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default=ESTADO_PROGRAMADA)

    class Meta:
        db_table = 'cronograma_sesiones'
        verbose_name = 'Sesion'
        verbose_name_plural = 'Sesiones'
        ordering = ['-fecha_hora']

    def __str__(self):
        return f'{self.id_tipo} - {self.fecha_hora:%Y-%m-%d %H:%M}'

    @property
    def cupos_ocupados(self):
        return max(self.cupos_max - self.cupos_disponibles, 0)


# ==========================================================================
# ASISTENCIA (tabla: asistencia_detalle)
# ==========================================================================

class Asistencia(models.Model):
    """
    Registro de asistencia de un estudiante a una sesion.

    `horas_ganadas` es la columna que alimenta el total de horas sociales,
    y solo cuenta cuando el docente la marca como 'Cumplida'.
    """

    CONFIRMACION_PENDIENTE = 'Pendiente'
    CONFIRMACION_ASISTE = 'Asistira'
    CONFIRMACION_NO_ASISTE = 'No asistira'
    CONFIRMACION_CHOICES = [
        (CONFIRMACION_PENDIENTE, 'Pendiente'),
        (CONFIRMACION_ASISTE, 'Asistira'),
        (CONFIRMACION_NO_ASISTE, 'No asistira'),
    ]

    VALIDACION_POR_VALIDAR = 'Por Validar'
    VALIDACION_CUMPLIDA = 'Cumplida'
    VALIDACION_INASISTENCIA = 'Inasistencia'
    VALIDACION_CHOICES = [
        (VALIDACION_POR_VALIDAR, 'Por Validar'),
        (VALIDACION_CUMPLIDA, 'Cumplida'),
        (VALIDACION_INASISTENCIA, 'Inasistencia'),
    ]

    id_registro = models.AutoField(primary_key=True)
    id_sesion = models.ForeignKey(
        Sesion, on_delete=models.CASCADE, db_column='id_sesion',
        related_name='asistencias',
    )
    id_estudiante = models.ForeignKey(
        Usuario, on_delete=models.CASCADE, db_column='id_estudiante',
        related_name='asistencias',
        limit_choices_to={'rol': Usuario.ROL_ESTUDIANTE},
        verbose_name='estudiante',
    )
    confirmacion = models.CharField(
        max_length=20, choices=CONFIRMACION_CHOICES, default=CONFIRMACION_PENDIENTE,
    )
    justificacion = models.TextField(blank=True, null=True)
    comentario_profesor = models.TextField(blank=True, null=True)
    validacion_prof = models.CharField(
        max_length=20, choices=VALIDACION_CHOICES, default=VALIDACION_POR_VALIDAR,
    )
    horas_ganadas = models.PositiveIntegerField(default=0)
    fecha_confirmacion = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'asistencia_detalle'
        verbose_name = 'Asistencia'
        verbose_name_plural = 'Asistencias'
        # Un estudiante no puede tener dos registros en la misma sesion.
        constraints = [
            models.UniqueConstraint(
                fields=['id_sesion', 'id_estudiante'],
                name='uniq_asistencia_sesion_estudiante',
            ),
        ]

    def __str__(self):
        return f'{self.id_estudiante} en {self.id_sesion} -> {self.validacion_prof}'


# ==========================================================================
# LISTA DE ESPERA (tabla: lista_esperaa)
# ==========================================================================

class ListaEspera(models.Model):
    """Cola de espera cuando una sesion se queda sin cupos."""

    id_espera = models.AutoField(primary_key=True)
    id_sesion = models.ForeignKey(
        Sesion, on_delete=models.CASCADE, db_column='id_sesion',
        related_name='lista_espera',
    )
    id_estudiante = models.ForeignKey(
        Usuario, on_delete=models.CASCADE, db_column='id_estudiante',
        related_name='lista_espera',
        limit_choices_to={'rol': Usuario.ROL_ESTUDIANTE},
    )
    fecha_inscripcion = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'lista_esperaa'
        verbose_name = 'Registro en lista de espera'
        verbose_name_plural = 'Lista de espera'
        ordering = ['fecha_inscripcion']

    def __str__(self):
        return f'{self.id_estudiante} esperando {self.id_sesion}'


# ==========================================================================
# SOLICITUD DE RECUPERACION (tabla: solicitudes_recuperacion_maestros)
# ==========================================================================

class SolicitudRecuperacion(models.Model):
    """
    Solicitud de 'olvide mi contrasena' de un docente.

    Dos caminos hasta la fecha:

    1. Flujo heredado: el docente envia los datos -> 'Pendiente' -> un
       directivo la aprueba desde el admin -> 'Autorizado'.
    2. Flujo del formulario decorado: el paso 2 de la pagina (fijar la
       contrasena nueva) cierra la solicitud en el mismo momento ->
       'Restablecida', con `fecha_resolucion` marcada.

    En ningun caso se guarda la contrasena aqui: solo la trazabilidad. La
    clave nueva vive cifrada (PBKDF2) en `usuariosa.password`.
    """

    ESTADO_PENDIENTE = 'Pendiente'
    ESTADO_AUTORIZADO = 'Autorizado'
    ESTADO_RESTABLECIDA = 'Restablecida'
    ESTADO_CHOICES = [
        (ESTADO_PENDIENTE, 'Pendiente'),
        (ESTADO_AUTORIZADO, 'Autorizado'),
        (ESTADO_RESTABLECIDA, 'Restablecida'),
    ]

    id = models.AutoField(primary_key=True)
    usuario = models.CharField(max_length=50, help_text='Codigo o correo del docente.')
    nombre_completo = models.CharField(max_length=150)
    telefono = models.CharField(max_length=20)
    asignatura = models.CharField(max_length=100)
    fecha_solicitud = models.DateTimeField(auto_now_add=True)
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default=ESTADO_PENDIENTE)
    fecha_resolucion = models.DateTimeField(
        'fecha de resolucion', null=True, blank=True,
        help_text='Momento en que se fijo la contrasena nueva.',
    )

    class Meta:
        db_table = 'solicitudes_recuperacion_maestros'
        verbose_name = 'Solicitud de recuperacion'
        verbose_name_plural = 'Solicitudes de recuperacion'
        ordering = ['-fecha_solicitud']

    def __str__(self):
        return f'{self.usuario} ({self.estado})'
