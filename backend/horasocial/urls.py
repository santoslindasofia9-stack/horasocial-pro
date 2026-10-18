"""
URL configuration for horasocial project.

Rutas principales:
    /admin/                  -> panel de administracion (directivos)
    /docentes/...            -> modulo de docentes (login, registro, panel)
    /api/login-maestro       -> puente con el formulario HTML existente
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

from docentes import views as docentes_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('docentes/', include('docentes.urls')),

    # La raiz lleva al login del docente.
    path(
        '',
        RedirectView.as_view(pattern_name='docentes:login', permanent=False),
        name='inicio',
    ),

    # Compatibilidad: el HTML actual postea a /api/login-maestro
    # (mismos campos `username` y `password` del server.js original).
    path('api/login-maestro', docentes_views.api_login_maestro, name='api-login-maestro'),

    # El formulario de recuperacion envia JSON y espera {"success": true}.
    path(
        'api/recuperar-contrasena-maestro',
        docentes_views.api_recuperar_contrasena_maestro,
        name='api-recuperar-contrasena-maestro',
    ),

    # Paso 2 del mismo formulario: fija la contrasena nueva en `usuariosa`
    # y cierra la solicitud en `solicitudes_recuperacion_maestros`.
    path(
        'api/restablecer-contrasena-maestro',
        docentes_views.api_restablecer_contrasena_maestro,
        name='api-restablecer-contrasena-maestro',
    ),

    # El dashboard decorado pregunta quien tiene la sesion abierta, para
    # mostrar el nombre real en lugar de un placeholder.
    path(
        'api/sesion-actual',
        docentes_views.api_sesion_actual,
        name='api-sesion-actual',
    ),

    # Panel del docente con datos reales: estadisticas, brigadas y
    # asistencias que esperan validacion.
    path(
        'api/dashboard-maestro',
        docentes_views.api_dashboard_maestro,
        name='api-dashboard-maestro',
    ),

    # Estudiantes a cargo del docente con horas, estado e historial.
    path(
        'api/estudiantes-maestro',
        docentes_views.api_estudiantes_maestro,
        name='api-estudiantes-maestro',
    ),

    # Validar o rechazar una asistencia desde el panel (con los contadores
    # ya recalculados en la respuesta).
    path(
        'api/asistencia-accion',
        docentes_views.api_asistencia_accion,
        name='api-asistencia-accion',
    ),

    # Actividades que el docente registra y sube (tabla sesionservicio).
    path(
        'api/sesionservicio-maestro',
        docentes_views.api_sesionservicio_maestro,
        name='api-sesionservicio-maestro',
    ),

    # Completar o cancelar una actividad registrada.
    path(
        'api/sesionservicio-accion',
        docentes_views.api_sesionservicio_accion,
        name='api-sesionservicio-accion',
    ),

    # Reporte semanal o mensual de horas y pendientes del docente.
    path(
        'api/reporte-maestro',
        docentes_views.api_reporte_maestro,
        name='api-reporte-maestro',
    ),
]

# En desarrollo el runserver sirve las evidencias subidas desde MEDIA_ROOT.
# En produccion esto lo hace el servidor web (nginx/apache), por eso solo
# se agrega cuando DEBUG esta encendido.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
