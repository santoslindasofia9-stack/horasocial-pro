"""Rutas del modulo de Docentes."""

from django.urls import path

from . import views

app_name = 'docentes'

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('registro/', views.registro_view, name='registro'),
    path('recuperar/', views.recuperar_view, name='recuperar'),
    path('panel/', views.dashboard_view, name='dashboard'),
    path('cambiar-contrasena/', views.cambiar_contrasena_view, name='cambiar_contrasena'),
]
