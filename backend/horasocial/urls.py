"""
URL configuration for horasocial project.

Rutas principales:
    /admin/                  -> panel de administracion (directivos)
    /docentes/...            -> modulo de docentes (login, registro, panel)
    /api/login-maestro       -> puente con el formulario HTML existente
"""

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
]
