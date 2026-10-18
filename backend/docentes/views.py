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

import json
from functools import wraps

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
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

                # 'next' lo agrega login_required al redirigir. Se valida
                # contra el host actual: sin esto se puede usar el login para
                # mandar al usuario a un sitio externo (redireccion abierta).
                siguiente = request.GET.get('next')
                if not url_has_allowed_host_and_scheme(
                    siguiente,
                    allowed_hosts={request.get_host()},
                    require_https=request.is_secure(),
                ):
                    siguiente = reverse('docentes:dashboard')
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

def _url_login_decorado():
    """
    URL del formulario decorado de login, o cadena vacia si no esta configurada.

    El destino sale de settings y NUNCA de la peticion: un destino que viniera
    del cliente seria una redireccion abierta.
    """
    return getattr(settings, 'LOGIN_DOCENTE_URL', '')


def _respuesta_login_fallido():
    """
    Devuelve al formulario decorado con la marca de error.

    Sin `LOGIN_DOCENTE_URL` configurada cae al login de Django, que es el
    comportamiento historico. Con ella, el docente vuelve al formulario que
    estaba usando en vez de aterrizar en una pantalla plana que ofrece
    "olvide mi contrasena".
    """
    destino = _url_login_decorado()
    if not destino:
        return redirect('docentes:login')

    separador = '&' if '?' in destino else '?'
    return HttpResponseRedirect('%s%serror=credenciales' % (destino, separador))


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
        return _respuesta_login_fallido()

    usuario = buscar_usuario(identificador)

    if usuario is not None and usuario.tiene_acceso:
        autenticado = authenticate(request, username=usuario.correo, password=password)
        if autenticado is not None:
            usuario.reiniciar_intentos()
            login(request, autenticado)

            # El formulario decorado vive en otro puerto (:3000). Con una URL
            # configurada, el docente aterriza directo en el dashboard
            # decorado con la sesion ya abierta; sin ella, en el panel de
            # Django. El destino sale de settings y NUNCA de la peticion: un
            # destino que viniera del cliente seria una redireccion abierta.
            destino = getattr(settings, 'DASHBOARD_DOCENTE_URL', '')
            if destino:
                return HttpResponseRedirect(destino)
            return HttpResponseRedirect(reverse('docentes:dashboard'))

    messages.error(request, MENSAJE_CREDENCIALES)
    return _respuesta_login_fallido()


# ==========================================================================
# API JSON PARA LAS PAGINAS ESTATICAS (server.js en :3000, Live Server :5500)
# ==========================================================================

# Origenes autorizados a consumir la API desde otro puerto. Si el frontend se
# publica en otro dominio, agregarlo aqui.
ORIGENES_PERMITIDOS = {
    'http://localhost:3000',
    'http://127.0.0.1:3000',
    'http://localhost:5500',
    'http://127.0.0.1:5500',
}


def habilita_cors(view):
    """
    Agrega las cabeceras CORS a la respuesta.

    Las paginas decoradas se sirven desde otro puerto (server.js en el 3000),
    asi que el navegador aplica la politica de mismo origen: sin
    `Access-Control-Allow-Origin` descarta la respuesta aunque el servidor la
    haya generado bien.
    """

    @wraps(view)
    def envoltura(request, *args, **kwargs):
        respuesta = view(request, *args, **kwargs)
        origen = request.headers.get('Origin', '')
        if origen in ORIGENES_PERMITIDOS:
            respuesta['Access-Control-Allow-Origin'] = origen
            respuesta['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
            respuesta['Access-Control-Allow-Headers'] = 'Content-Type'
            # El dashboard decorado manda la cookie de sesion en el fetch
            # (`credentials: 'include'`). Sin esta cabecera el navegador
            # descarta la respuesta. Con credenciales NO se puede responder
            # '*': hay que devolver el origen exacto, como se hace arriba.
            respuesta['Access-Control-Allow-Credentials'] = 'true'
            respuesta['Vary'] = 'Origin'
        return respuesta

    return envoltura


def primer_error(formulario):
    """Primer mensaje de error de un formulario, para responder en JSON."""
    for errores in formulario.errors.get_json_data().values():
        if errores:
            return errores[0].get('message', 'Datos invalidos.')
    return 'Datos invalidos.'


@csrf_exempt
@habilita_cors
@require_http_methods(['POST', 'OPTIONS'])
def api_recuperar_contrasena_maestro(request):
    """
    Endpoint JSON del formulario 'olvide mi contrasena'.

    El HTML envia {usuario, nombre, telefono, asignatura} como JSON y espera
    {"success": true}. Reutiliza `RecuperarContrasenaForm`, de modo que aplican
    exactamente las mismas validaciones que el formulario de Django: telefono
    de minimo 7 digitos y sin solicitudes pendientes duplicadas.
    """

    if request.method == 'OPTIONS':
        # Preflight que dispara el navegador por Content-Type: application/json.
        return HttpResponse(status=204)

    try:
        datos = json.loads(request.body or b'{}')
    except (TypeError, ValueError):
        return JsonResponse(
            {'success': False, 'error': 'El cuerpo de la peticion no es JSON valido.'},
            status=400,
        )

    if not isinstance(datos, dict):
        return JsonResponse(
            {'success': False, 'error': 'El cuerpo de la peticion debe ser un objeto JSON.'},
            status=400,
        )

    # El HTML manda `nombre`; el modelo lo llama `nombre_completo`.
    formulario = RecuperarContrasenaForm({
        'usuario': str(datos.get('usuario', '')).strip(),
        'nombre_completo': str(datos.get('nombre', '')).strip(),
        'telefono': str(datos.get('telefono', '')).strip(),
        'asignatura': str(datos.get('asignatura', '')).strip(),
    })

    if not formulario.is_valid():
        return JsonResponse(
            {'success': False, 'error': primer_error(formulario)},
            status=400,
        )

    solicitud = formulario.save()
    return JsonResponse({'success': True, 'folio': solicitud.id})


@habilita_cors
@require_http_methods(['GET', 'OPTIONS'])
def api_sesion_actual(request):
    """
    Devuelve quien tiene la sesion abierta.

    El dashboard decorado la consulta con `credentials: 'include'` para
    mostrar el nombre real del docente en lugar del nombre por defecto de la
    maqueta, y para no quedar accesible sin sesion.

    Detalle de cookies: el frontend (:3000) y el backend (:8000) son ORIGENES
    distintos, pero el MISMO SITIO (SameSite no compara puertos). Por eso la
    cookie de sesion viaja en el fetch. Requisito: usar `127.0.0.1` en los dos
    lados, porque `localhost` y `127.0.0.1` SI son sitios distintos.
    """

    if request.method == 'OPTIONS':
        # Preflight que dispara el navegador por el fetch con credenciales.
        return HttpResponse(status=204)

    if not request.user.is_authenticated:
        return JsonResponse({'autenticado': False})

    return JsonResponse({
        'autenticado': True,
        'id_usuario': request.user.pk,
        'nombre': request.user.nombre_completo,
        'correo': request.user.correo,
        'rol': request.user.rol,
        'es_docente': request.user.es_docente,
    })
