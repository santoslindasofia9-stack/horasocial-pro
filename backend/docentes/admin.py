"""Panel de administracion del modulo de Docentes."""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import (
    Actividad,
    Asistencia,
    ListaEspera,
    Sesion,
    SolicitudRecuperacion,
    Usuario,
)


@admin.register(Usuario)
class UsuarioAdmin(BaseUserAdmin):
    """Administracion del usuario unico (el correo es el identificador)."""

    ordering = ['nombre_completo']
    list_display = [
        'correo', 'nombre_completo', 'rol', 'codigo',
        'estado_cuenta', 'intentos_fallidos', 'is_staff',
    ]
    list_filter = ['rol', 'estado_cuenta', 'is_staff', 'is_superuser']
    search_fields = ['correo', 'nombre_completo', 'codigo']
    readonly_fields = ['last_login', 'date_joined']

    fieldsets = (
        (None, {'fields': ('correo', 'password')}),
        ('Datos personales', {'fields': ('nombre_completo', 'codigo', 'grado')}),
        ('Modulo de horas sociales', {
            'fields': ('rol', 'estado_cuenta', 'intentos_fallidos'),
        }),
        ('Permisos', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        ('Fechas', {'fields': ('last_login', 'date_joined')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('correo', 'nombre_completo', 'rol', 'password1', 'password2'),
        }),
    )

    actions = ['desbloquear_cuentas']

    @admin.action(description='Desbloquear cuentas seleccionadas')
    def desbloquear_cuentas(self, request, queryset):
        """Pone intentos_fallidos en 0 y estado_cuenta en Activo."""
        actualizadas = queryset.update(
            intentos_fallidos=0,
            estado_cuenta=Usuario.ESTADO_ACTIVO,
        )
        self.message_user(request, f'{actualizadas} cuenta(s) desbloqueada(s).')


@admin.register(Actividad)
class ActividadAdmin(admin.ModelAdmin):
    list_display = ['nombre_actividad', 'categoria']
    list_filter = ['categoria']
    search_fields = ['nombre_actividad']


@admin.register(Sesion)
class SesionAdmin(admin.ModelAdmin):
    list_display = [
        'id_sesion', 'id_tipo', 'id_profesor',
        'fecha_hora', 'ubicacion', 'cupos_disponibles', 'estado',
    ]
    list_filter = ['estado', 'id_tipo']
    search_fields = ['ubicacion', 'id_profesor__nombre_completo']
    date_hierarchy = 'fecha_hora'
    autocomplete_fields = ['id_profesor', 'id_tipo']


@admin.register(Asistencia)
class AsistenciaAdmin(admin.ModelAdmin):
    list_display = [
        'id_registro', 'id_estudiante', 'id_sesion',
        'confirmacion', 'validacion_prof', 'horas_ganadas',
    ]
    list_filter = ['validacion_prof', 'confirmacion']
    search_fields = [
        'id_estudiante__nombre_completo',
        'id_estudiante__codigo',
        'id_sesion__id_tipo__nombre_actividad',
    ]
    autocomplete_fields = ['id_estudiante', 'id_sesion']


@admin.register(ListaEspera)
class ListaEsperaAdmin(admin.ModelAdmin):
    list_display = ['id_espera', 'id_sesion', 'id_estudiante', 'fecha_inscripcion']
    search_fields = ['id_estudiante__nombre_completo', 'id_estudiante__codigo']
    autocomplete_fields = ['id_estudiante', 'id_sesion']


@admin.register(SolicitudRecuperacion)
class SolicitudRecuperacionAdmin(admin.ModelAdmin):
    """Panel donde el directivo autoriza los 'olvide mi contrasena'."""

    list_display = [
        'id', 'usuario', 'nombre_completo',
        'telefono', 'asignatura', 'fecha_solicitud', 'estado',
    ]
    list_filter = ['estado', 'asignatura']
    search_fields = ['usuario', 'nombre_completo', 'telefono']
    readonly_fields = ['fecha_solicitud']
    actions = ['autorizar_solicitudes']

    @admin.action(description='Autorizar solicitudes seleccionadas')
    def autorizar_solicitudes(self, request, queryset):
        actualizadas = queryset.update(estado=SolicitudRecuperacion.ESTADO_AUTORIZADO)
        self.message_user(
            request,
            f'{actualizadas} solicitud(es) autorizada(s). '
            'El docente ya puede cambiar su contrasena desde el login.',
        )
