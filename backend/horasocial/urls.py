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
from django.views.static import serve as serve_static

from docentes import views as docentes_views

# Raiz del frontend decorado (un nivel arriba de backend/).
FRONTEND_DIR = settings.BASE_DIR.parent


def _pagina_decorada(carpeta):
    """Sirve el index.html de una carpeta del frontend decorado."""
    return {
        'document_root': str(FRONTEND_DIR / carpeta),
        'path': 'index.html',
    }


urlpatterns = [
    path('admin/', admin.site.urls),
    path('docentes/', include('docentes.urls')),

    # ------------------------------------------------------------------
    # PAGINAS DECORADAS SERVIDAS POR DJANGO
    #
    # El login decorado postea a /api/login-maestro y Django lo redirige a
    # /profesor/dashboard en el MISMO origen. Resultado: el flujo completo
    # (login -> dashboard con la sesion del docente) funciona con solo
    # `python manage.py runserver`, sin depender de server.js en :3000 y sin
    # problemas de cookies entre puertos u hosts distintos.
    # ------------------------------------------------------------------
    path(
        'profesor/login',
        serve_static,
        _pagina_decorada('login_maestro_horasocial_pro'),
        name='profesor-login',
    ),
    path(
        'profesor/recuperar-contrasena',
        serve_static,
        _pagina_decorada('recuperar_contrasena_maestro_horasocial_pro'),
        name='profesor-recuperar',
    ),
    path(
        'profesor/dashboard',
        serve_static,
        _pagina_decorada('dashboard_maestro_horasocial_pro'),
        name='profesor-dashboard',
    ),
    path(
        'profesor/estudiantes',
        serve_static,
        _pagina_decorada('gestion_estudiantes_maestro_horasocial_pro'),
        name='profesor-estudiantes',
    ),
    path(
        'profesor/tecnica',
        serve_static,
        _pagina_decorada('gestion_tecnica_maestro_horasocial_pro'),
        name='profesor-tecnica',
    ),
    path(
        'profesor/chat',
        serve_static,
        _pagina_decorada('chat_maestro_horasocial_pro'),
        name='profesor-chat',
    ),
    path(
        'profesor/mensajes',
        serve_static,
        _pagina_decorada('mensajes_maestro_horasocial_pro'),
        name='profesor-mensajes',
    ),

    # La raiz lleva directo al login decorado.
    path(
        '',
        RedirectView.as_view(url='/profesor/login', permanent=False),
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

    # Bandeja de mensajes (tabla mensajes): hilos del docente con sus
    # estudiantes. El POST envia un mensaje y rechaza el lenguaje ofensivo.
    path(
        'api/mensajes-maestro',
        docentes_views.api_mensajes_maestro,
        name='api-mensajes-maestro',
    ),

    # Conversacion completa con un estudiante a cargo.
    path(
        'api/chat-maestro',
        docentes_views.api_chat_maestro,
        name='api-chat-maestro',
    ),
]

# En desarrollo el runserver sirve las evidencias subidas desde MEDIA_ROOT.
# En produccion esto lo hace el servidor web (nginx/apache), por eso solo
# se agrega cuando DEBUG esta encendido.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

    # Imagenes del frontend decorado (avatares, logos locales). Las paginas
    # servidas en /profesor/* las referencian como ../img/..., que resuelve a
    # /img/...
    urlpatterns += [
        path(
            'img/<path:path>',
            serve_static,
            {'document_root': str(FRONTEND_DIR / 'img')},
        ),
    ]
