"""
Vistas del modulo de Docentes - HORASOCIAL PRO.

Flujo de autenticacion:

    POST /docentes/login/  ->  validar formulario
                            ->  resolver usuario por correo o codigo
                            ->  verificar estado de la cuenta
                            ->  authenticate() contra el hash en MySQL
                            ->  login() y redireccion al panel

La contrasena nunca se compara en texto plano: `authenticate()` recalcula el
hash (PBKDF2) y lo contrasta con la columna `password` de la tabla `usuariosa`.
"""

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_http_methods

from .forms import (
    MENSAJE_CREDENCIALES,
    CambiarContrasenaForm,
    LoginForm,
    RecuperarContrasenaForm,
    RegistroDocenteForm,
    buscar_usuario,
)
from .models import Docente, Usuario


# ==========================================================================
# SESION
# ==========================================================================

@require_http_methods(['GET', 'POST'])
def login_view(request):
    """Login real del docente validando contra la base de datos MySQL."""

    # Si ya tiene sesion abierta, no tiene sentido mostrarle el login.
    if request.user.is_authenticated:
        return redirect('docentes:dashboard')

    form = LoginForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        identificador = form.cleaned_data['identificador']
        password = form.cleaned_data['password']
        usuario = buscar_usuario(identificador)

        if usuario is None:
            # Mensaje generico: no revelamos si el correo existe.
            messages.error(request, MENSAJE_CREDENCIALES)

        elif usuario.estado_cuenta == Usuario.ESTADO_BLOQUEADO:
            messages.error(
                request,
                'La cuenta esta bloqueada por demasiados intentos fallidos. '
                'Solicita la recuperacion de contrasena.',
            )

        elif not usuario.is_active:
            messages.error(request, 'La cuenta esta inactiva. Contacta al directivo.')

        else:
            # Aqui ocurre la verificacion real del hash contra MySQL.
            autenticado = authenticate(
                request, username=usuario.correo, password=password,
            )

            if autenticado is None:
                maximo = getattr(settings, 'MAX_INTENTOS_FALLIDOS', 5)
                usuario.registrar_intento_fallido(maximo)
                restantes = maximo - usuario.intentos_fallidos
                if restantes > 0:
                    messages.error(
                        request,
                        f'{MENSAJE_CREDENCIALES} Te quedan {restantes} intento(s).',
                    )
                else:
                    messages.error(
                        request,
                        'Cuenta bloqueada por demasiados intentos fallidos.',
                    )
            else:
                usuario.reiniciar_intentos()
                login(request, autenticado)

                if not autenticado.es_docente:
                    messages.warning(
                        request,
                        'Tu cuenta no tiene el rol de Docente, pero iniciaste sesion.',
                    )
                else:
                    messages.success(request, f'Bienvenido, {autenticado.nombre_completo}.')

                siguiente = request.GET.get('next') or reverse('docentes:dashboard')
                return redirect(siguiente)

    return render(request, 'docentes/login.html', {'form': form})


@require_POST
def logout_view(request):
    """Cierra la sesion del docente."""
    logout(request)
    messages.info(request, 'Cerraste sesion correctamente.')
    return redirect('docentes:login')


# ==========================================================================
# REGISTRO
# ==========================================================================

@require_http_methods(['GET', 'POST'])
def registro_view(request):
    """Registro de docentes. La contrasena se guarda cifrada."""

    if request.user.is_authenticated:
        return redirect('docentes:dashboard')

    form = RegistroDocenteForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        docente = form.save()
        messages.success(
            request,
            f'Docente registrado: {docente.nombre_completo}. Ya puedes iniciar sesion.',
        )
        return redirect('docentes:login')

    return render(request, 'docentes/registro.html', {'form': form})


# ==========================================================================
# RECUPERACION DE CONTRASENA
# ==========================================================================

@require_http_methods(['GET', 'POST'])
def recuperar_view(request):
    """
    'Olvide mi contrasena'.

    No cambia la contrasena directamente: crea una solicitud en la tabla
    `solicitudes_recuperacion_maestros` con estado 'Pendiente', que un
    directivo autoriza desde el panel de administracion.
    """

    form = RecuperarContrasenaForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        solicitud = form.save()
        messages.success(
            request,
            f'Solicitud registrada (folio #{solicitud.id}). '
            'Un directivo la revisara y te autorizara el cambio.',
        )
        return redirect('docentes:login')

    return render(request, 'docentes/recuperar.html', {'form': form})


# ==========================================================================
# PANEL DEL DOCENTE
# ==========================================================================

@login_required
def dashboard_view(request):
    """Panel del docente autenticado con su resumen del modulo."""

    usuario = request.user
    contexto = {'usuario': usuario}

    if usuario.es_docente:
        # Docente es un proxy de Usuario: misma fila, pero expone los metodos
        # del modulo (brigadas_asignadas, estudiantes_a_cargo, resumen()).
        docente = Docente.objects.get(pk=usuario.pk)
        contexto.update({
            'es_docente': True,
            'brigadas': docente.brigadas_asignadas,
            'estudiantes': docente.estudiantes_a_cargo,
            'resumen': docente.resumen(),
        })
    else:
        contexto.update({
            'es_docente': False,
            'horas_registradas': getattr(usuario, 'horas_registradas', 0),
        })

    return render(request, 'docentes/dashboard.html', contexto)


@login_required
@require_http_methods(['GET', 'POST'])
def cambiar_contrasena_view(request):
    """Cambio de contrasena del docente autenticado."""

    form = CambiarContrasenaForm(request.user, request.POST or None)

    if request.method == 'POST' and form.is_valid():
        form.save()
        # Mantiene viva la sesion actual tras cambiar el hash.
        update_session_auth_hash(request, request.user)
        messages.success(request, 'Contrasena actualizada correctamente.')
        return redirect('docentes:dashboard')

    return render(request, 'docentes/cambiar_contrasena.html', {'form': form})


# ==========================================================================
# COMPATIBILIDAD CON EL FRONTEND EXISTENTE
# ==========================================================================

@csrf_exempt
@require_POST
def api_login_maestro(request):
    """
    Puente con el formulario HTML actual (`action="/api/login-maestro"`),
    que envia los campos `username` y `password`.

    NOTA DE SEGURIDAD: esta vista queda exenta de CSRF para que el formulario
    existente (que no incluye {% csrf_token %}) siga funcionando. Lo correcto
    es migrar el HTML al formulario de Django y quitar `csrf_exempt`.
    """

    identificador = request.POST.get('username', '').strip()
    password = request.POST.get('password', '')

    if not identificador or not password:
        messages.error(request, 'Debes ingresar usuario y contrasena.')
        return redirect('docentes:login')

    usuario = buscar_usuario(identificador)

    if usuario is not None and usuario.tiene_acceso:
        autenticado = authenticate(request, username=usuario.correo, password=password)
        if autenticado is not None:
            usuario.reiniciar_intentos()
            login(request, autenticado)
            return HttpResponseRedirect(reverse('docentes:dashboard'))

    messages.error(request, MENSAJE_CREDENCIALES)
    return redirect('docentes:login')
