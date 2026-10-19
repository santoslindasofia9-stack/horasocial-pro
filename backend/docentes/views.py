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
import os
import unicodedata
from datetime import datetime, time, timedelta
from functools import wraps

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Sum
from django.db.models.functions import Coalesce
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_http_methods

from .forms import (
    MENSAJE_CREDENCIALES,
    CambiarContrasenaForm,
    LoginForm,
    RecuperarContrasenaForm,
    RegistroDocenteForm,
    RestablecerContrasenaForm,
    buscar_usuario,
)
from .models import (
    Actividad,
    Asistencia,
    Docente,
    Mensaje,
    Sesion,
    SolicitudRecuperacion,
    Usuario,
    SesionServicio,
)


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


def _texto_normalizado(valor):
    """
    Minusculas, sin acentos y con los espacios colapsados.

    Compara el nombre que el docente escribe en el formulario decorado con el
    guardado en `usuariosa.nombre_completo`: 'Ana Maria' y 'ana   maría'
    tienen que resolver a la misma cadena, o el segundo paso rechazaria a un
    docente real por una diferencia de tildes.
    """
    texto = ' '.join(str(valor or '').split()).casefold()
    return ''.join(
        caracter
        for caracter in unicodedata.normalize('NFKD', texto)
        if not unicodedata.combining(caracter)
    )


def _respuesta_datos_no_coinciden():
    """
    Unico mensaje para 'no existe', 'no es docente', 'cuenta inactiva' o
    'el nombre no coincide'. Responder distinto por cada caso le diria a un
    tercero cual identificador si existe en la base.
    """
    return JsonResponse(
        {
            'success': False,
            'error': 'Los datos no coinciden con ninguna cuenta registrada.',
        },
        status=403,
    )


@csrf_exempt
@habilita_cors
@require_http_methods(['POST', 'OPTIONS'])
def api_restablecer_contrasena_maestro(request):
    """
    Paso 2 del formulario decorado: fija la contrasena nueva.

    Recibe los datos del paso 1 (para revalidar la identidad) mas las dos
    contrasenas. La identidad se prueba con codigo/correo + nombre completo;
    el telefono y la asignatura no se pueden contrastar porque `usuariosa` no
    tiene esas columnas: se guardan en la solicitud como dato de contacto.

    Al aprobar: cifra la clave nueva con PBKDF2 en `usuariosa.password`,
    marca la solicitud como 'Restablecida' con su `fecha_resolucion` y
    reinicia los intentos fallidos, para que una cuenta bloqueada por
    equivocaciones vuelva a poder entrar. Nunca se escribe la clave en texto
    plano ni en la tabla de solicitudes.
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

    identificador = str(datos.get('usuario', '')).strip()
    nombre = str(datos.get('nombre', '')).strip()
    telefono = str(datos.get('telefono', '')).strip()
    asignatura = str(datos.get('asignatura', '')).strip()
    password1 = str(datos.get('password1', ''))
    password2 = str(datos.get('password2', ''))

    # Mismos limites de columna que el modelo, para no depender del modo
    # STRICT_TRANS_TABLES para rechazar un dato largo.
    if not identificador or len(identificador) > 50:
        return _respuesta_datos_no_coinciden()
    if len(nombre) > 150 or len(telefono) > 20 or len(asignatura) > 100:
        return JsonResponse(
            {'success': False, 'error': 'Algun dato supera el tamano maximo permitido.'},
            status=400,
        )

    digitos = ''.join(caracter for caracter in telefono if caracter.isdigit())
    if len(digitos) < 7:
        return JsonResponse(
            {'success': False, 'error': 'Ingresa un telefono valido (minimo 7 digitos).'},
            status=400,
        )

    docente = buscar_usuario(identificador)
    if (
        docente is None
        or not docente.es_docente
        or not docente.is_active
        or _texto_normalizado(docente.nombre_completo) != _texto_normalizado(nombre)
    ):
        return _respuesta_datos_no_coinciden()

    formulario = RestablecerContrasenaForm(
        docente, {'password1': password1, 'password2': password2},
    )
    if not formulario.is_valid():
        return JsonResponse(
            {'success': False, 'error': primer_error(formulario)},
            status=400,
        )

    with transaction.atomic():
        # La solicitud del paso 1 (si existe) se cierra; si no, se crea ya
        # resuelta, para que el paso 2 pueda repetirse tras recargar la pagina.
        solicitud = (
            SolicitudRecuperacion.objects
            .filter(usuario__iexact=identificador)
            .order_by('-fecha_solicitud')
            .first()
        )
        if solicitud is None:
            solicitud = SolicitudRecuperacion(usuario=identificador)

        solicitud.nombre_completo = docente.nombre_completo
        solicitud.telefono = telefono
        solicitud.asignatura = asignatura
        solicitud.estado = SolicitudRecuperacion.ESTADO_RESTABLECIDA
        solicitud.fecha_resolucion = timezone.now()
        solicitud.save()

        # set_password() cifra con PBKDF2 + salt. La columna `password` solo
        # guarda el hash, nunca la clave que acaba de escribir el docente.
        docente.set_password(password1)
        docente.save(update_fields=['password'])
        docente.reiniciar_intentos()

    return JsonResponse({'success': True})


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


# ==========================================================================
# API JSON DEL PANEL DEL DOCENTE (datos reales de MySQL)
# ==========================================================================

def _docente_en_sesion(request):
    """
    Docente con la sesion abierta, o None.

    El panel no es publico: sin sesion, o con una sesion de otro rol, la
    respuesta es 401 con la misma marca que el frontend usa para volver
    al login.
    """
    usuario = request.user
    if not usuario.is_authenticated or not usuario.es_docente:
        return None
    # Se devuelve la vista proxy `Docente` para reutilizar sus propiedades
    # (estudiantes a cargo, horas validadas) en lugar de repetir las queries.
    return Docente.objects.filter(pk=usuario.pk).first()


def _respuesta_sin_sesion():
    return JsonResponse({'autenticado': False, 'error': 'sesion'}, status=401)


def _formato_corta(fecha):
    """Fecha local 'YYYY-MM-DD HH:MM' (el panel la pinta tal cual)."""
    if not fecha:
        return None
    return timezone.localtime(fecha).strftime('%Y-%m-%d %H:%M')


def _rango(dias):
    """
    Rango local [desde, hasta] de los ultimos `dias` dias incluyendo hoy.

    Devuelve tambien los limites como datetimes aware [inicio, fin) para
    filtrar en base de datos sin depender de la zona del servidor.
    """
    hasta = timezone.localdate()
    desde = hasta - timedelta(days=dias - 1)
    inicio = timezone.make_aware(datetime.combine(desde, time.min))
    fin = timezone.make_aware(datetime.combine(hasta + timedelta(days=1), time.min))
    return desde, hasta, inicio, fin


def _asistencias_en(queryset, inicio, fin):
    """
    Asistencias con fecha de referencia dentro del rango [inicio, fin).

    La fecha de referencia es la confirmacion del estudiante y, si no hay
    registro de confirmacion, la fecha de la sesion: una validacion sin
    `fecha_confirmacion` no debe desaparecer del reporte.
    """
    return (
        queryset
        .annotate(fecha_ref=Coalesce('fecha_confirmacion', 'id_sesion__fecha_hora'))
        .filter(fecha_ref__gte=inicio, fecha_ref__lt=fin)
    )


def _suma_horas(queryset):
    return queryset.aggregate(total=Sum('horas_ganadas'))['total'] or 0


def _pendientes_de(docente):
    return Asistencia.objects.filter(
        id_sesion__id_profesor=docente,
        validacion_prof=Asistencia.VALIDACION_POR_VALIDAR,
    )


def _actividades_de(docente):
    return (
        Actividad.objects.filter(sesiones__id_profesor=docente)
        .distinct()
        .order_by('nombre_actividad')
    )


def _porcentaje(horas, meta):
    if not meta:
        return 0
    return max(0, min(100, round(horas / meta * 100)))


def _estadisticas_panel(docente):
    """Los cuatro contadores que el panel repite en cada respuesta."""
    return {
        'estudiantes': docente.estudiantes_a_cargo.count(),
        'actividades': docente.sesiones_dirigidas.values('id_tipo').distinct().count(),
        'horas_totales': docente.total_horas_validadas(),
        'pendientes': _pendientes_de(docente).count(),
    }


def _brigadas_panel(docente):
    """Sesiones del docente agrupadas por actividad (brigada)."""
    brigadas = []
    ahora = timezone.now()
    for actividad in _actividades_de(docente):
        sesiones = docente.sesiones_dirigidas.filter(id_tipo=actividad)
        asistencias = Asistencia.objects.filter(
            id_sesion__id_profesor=docente,
            id_sesion__id_tipo=actividad,
        )
        horas = _suma_horas(
            asistencias.filter(validacion_prof=Asistencia.VALIDACION_CUMPLIDA),
        )
        meta = sum(sesion.cupos_max for sesion in sesiones)
        proxima = (
            sesiones
            .filter(estado=Sesion.ESTADO_PROGRAMADA, fecha_hora__gt=ahora)
            .order_by('fecha_hora')
            .values_list('fecha_hora', flat=True)
            .first()
        )
        brigadas.append({
            'id': actividad.id_tipo,
            'nombre': actividad.nombre_actividad,
            'estudiantes': asistencias.values('id_estudiante').distinct().count(),
            'horas': horas,
            'meta': meta,
            'pct': _porcentaje(horas, meta),
            'proxima': _formato_corta(proxima),
        })
    return brigadas


def _filas_pendientes(docente):
    """Asistencias 'Por Validar' en orden cronologico de sesion."""
    registros = (
        _pendientes_de(docente)
        .select_related('id_estudiante', 'id_sesion__id_tipo')
        .order_by('id_sesion__fecha_hora', 'id_registro')
    )
    return [
        {
            'id_registro': registro.id_registro,
            'estudiante': registro.id_estudiante.nombre_completo,
            'actividad': registro.id_sesion.id_tipo.nombre_actividad,
            'fecha': _formato_corta(registro.id_sesion.fecha_hora),
            'ubicacion': registro.id_sesion.ubicacion,
            'confirmacion': registro.confirmacion,
        }
        for registro in registros
    ]


def _notificaciones(docente, stats):
    """Tres avisos en espanol derivados de los datos del panel."""
    proxima = (
        docente.sesiones_dirigidas
        .filter(estado=Sesion.ESTADO_PROGRAMADA, fecha_hora__gt=timezone.now())
        .order_by('fecha_hora')
        .first()
    )
    _, _, inicio, fin = _rango(7)
    horas_semana = _suma_horas(_asistencias_en(
        Asistencia.objects.filter(
            id_sesion__id_profesor=docente,
            validacion_prof=Asistencia.VALIDACION_CUMPLIDA,
        ),
        inicio,
        fin,
    ))
    return [
        {
            'id': 'n1',
            'txt': (
                f"{stats['pendientes']} asistencias esperan tu validacion"
                if stats['pendientes'] else 'No quedan asistencias por validar'
            ),
            'hora': 'hace 5 min',
            'leido': False,
        },
        {
            'id': 'n2',
            'txt': (
                f'Tu proxima sesion es {_formato_corta(proxima.fecha_hora)} '
                f'en {proxima.ubicacion}'
                if proxima else 'No tienes sesiones programadas'
            ),
            'hora': 'hoy',
            'leido': False,
        },
        {
            'id': 'n3',
            'txt': f'{horas_semana} horas validadas esta semana',
            'hora': 'hace 1 h',
            'leido': True,
        },
    ]


def _datos_panel(docente):
    """Carga completa que consume el panel decorado."""
    stats = _estadisticas_panel(docente)
    return {
        'autenticado': True,
        'docente': {'nombre': docente.nombre_completo},
        'stats': stats,
        'brigadas': _brigadas_panel(docente),
        'pendientes': _filas_pendientes(docente),
        'notifs': _notificaciones(docente, stats),
    }


MESES_CORTOS = [
    'ene', 'feb', 'mar', 'abr', 'may', 'jun',
    'jul', 'ago', 'sep', 'oct', 'nov', 'dic',
]

META_HORAS = 80


def _fecha_corta(fecha):
    """'12 oct' en la zona local, el formato que usa la lista de estudiantes."""
    if not fecha:
        return ''
    local = timezone.localtime(fecha)
    return f'{local.day} {MESES_CORTOS[local.month - 1]}'


def _historial_estudiante(docente, estudiante):
    """
    Movimientos del estudiante en las sesiones de este docente, del mas
    reciente al mas antiguo: fecha corta, horas y nombre de la actividad.
    """
    registros = (
        Asistencia.objects
        .filter(id_estudiante=estudiante, id_sesion__id_profesor=docente)
        .select_related('id_sesion__id_tipo')
        .order_by('-id_sesion__fecha_hora', '-id_registro')
    )
    return [
        {
            'f': _fecha_corta(registro.id_sesion.fecha_hora),
            'h': registro.horas_ganadas,
            'n': registro.id_sesion.id_tipo.nombre_actividad,
            'validacion': registro.validacion_prof,
        }
        for registro in registros
    ]


def _fila_estudiante(docente, estudiante):
    """
    Una fila de la pantalla de estudiantes: horas validadas, horas por
    validar y estado. Un estudiante esta 'Al dia' cuando ya tiene horas
    reconocidas y no le queda ninguna asistencia esperando validacion.
    """
    asistencias = Asistencia.objects.filter(
        id_estudiante=estudiante, id_sesion__id_profesor=docente,
    )
    horas = _suma_horas(
        asistencias.filter(validacion_prof=Asistencia.VALIDACION_CUMPLIDA),
    )
    pendientes = asistencias.filter(
        validacion_prof=Asistencia.VALIDACION_POR_VALIDAR,
    ).count()
    ultima = (
        asistencias
        .select_related('id_sesion__id_tipo')
        .order_by('-id_sesion__fecha_hora', '-id_registro')
        .first()
    )
    return {
        'id': estudiante.pk,
        'nombre': estudiante.nombre_completo,
        'codigo': estudiante.codigo or f'EST-{estudiante.pk}',
        'correo': estudiante.correo,
        'grado': estudiante.grado or '',
        'brigada': ultima.id_sesion.id_tipo.nombre_actividad if ultima else 'Sin brigada',
        'horas': horas,
        'pendientes': pendientes,
        'meta': META_HORAS,
        'pct': _porcentaje(horas, META_HORAS),
        'estado': 'Al dia' if (horas > 0 and pendientes == 0) else 'Pendiente',
        'historial': _historial_estudiante(docente, estudiante),
    }


def _datos_estudiantes(docente):
    """Carga completa que consume la pantalla de estudiantes."""
    filas = [
        _fila_estudiante(docente, estudiante)
        for estudiante in docente.estudiantes_a_cargo.order_by('nombre_completo')
    ]
    return {
        'autenticado': True,
        'docente': {'nombre': docente.nombre_completo},
        'stats': {
            'total': len(filas),
            'al_dia': sum(1 for fila in filas if fila['estado'] == 'Al dia'),
            'horas': sum(fila['horas'] for fila in filas),
            'meta': META_HORAS,
        },
        'estudiantes': filas,
    }


@csrf_exempt
@habilita_cors
@require_http_methods(['GET', 'OPTIONS'])
def api_estudiantes_maestro(request):
    """
    Estudiantes a cargo del docente con la sesion abierta.

    Cada fila trae las horas validadas, las que esperan validacion, la
    brigada de su ultimo movimiento y el historial de asistencias. Los
    contadores salen de las mismas asistencias que valida el panel, asi
    que aprobar una asistencia ahi se refleja aqui de inmediato.
    """

    if request.method == 'OPTIONS':
        # Preflight que dispara el navegador por Content-Type: application/json.
        return HttpResponse(status=204)

    docente = _docente_en_sesion(request)
    if docente is None:
        return _respuesta_sin_sesion()

    return JsonResponse(_datos_estudiantes(docente))


# ==========================================================================
# USUARIO SESION: actividades que registra el docente (tabla sesionservicio)
# ==========================================================================

def _iniciales(nombre):
    """Dos iniciales para los pines de estudiantes ('Valentina Rojas' -> VR)."""
    partes = [p for p in str(nombre).split() if p]
    if not partes:
        return '??'
    if len(partes) == 1:
        return partes[0][:2].upper()
    return (partes[0][0] + partes[1][0]).upper()


def _fila_sesionservicio(registro):
    """Una actividad registrada, con lo que el formulario vuelve a pintar."""
    return {
        'id': registro.id_registro,
        'titulo': registro.titulo,
        'nota': registro.descripcion or '',
        'taller': registro.taller,
        'fecha': registro.fecha.isoformat(),
        'hora': registro.hora.strftime('%H:%M'),
        'duracion': registro.duracion,
        'estado': registro.estado,
        'evidencia': registro.evidencia.name if registro.evidencia else '',
        'evidencia_url': registro.evidencia.url if registro.evidencia else '',
        'subida': _formato_corta(registro.fecha_registro),
        'estudiantes': [
            {
                'id': estudiante.pk,
                'nombre': estudiante.nombre_completo,
                'iniciales': _iniciales(estudiante.nombre_completo),
            }
            for estudiante in registro.estudiantes.all().order_by('nombre_completo')
        ],
    }


def _datos_sesionservicio(docente):
    """Registros de la tabla sesionservicio del docente en sesion."""
    registros = (
        SesionServicio.objects
        .filter(id_docente=docente)
        .prefetch_related('estudiantes')
    )
    filas = [_fila_sesionservicio(registro) for registro in registros]
    return {
        'autenticado': True,
        'docente': {'nombre': docente.nombre_completo},
        'tabla': 'sesionservicio',
        'stats': {
            'total': len(filas),
            'programadas': sum(1 for f in filas if f['estado'] == SesionServicio.ESTADO_PROGRAMADA),
            'completadas': sum(1 for f in filas if f['estado'] == SesionServicio.ESTADO_COMPLETADA),
        },
        'registros': filas,
    }


def _crear_sesionservicio(docente, datos, archivos):
    """
    Registra una actividad nueva. `datos` es un mapping tipo QueryDict o dict
    y `archivos` el request.FILES; devuelve (registro, error) con error None
    cuando salio bien.
    """
    titulo = str(datos.get('titulo', '') or '').strip()
    if not titulo:
        return None, 'Falta la tematica de la actividad.'

    taller = str(datos.get('taller', '') or '').strip() or 'Bodega general'

    fecha_cruda = str(datos.get('fecha', '') or '').strip()
    if not fecha_cruda:
        return None, 'Falta la fecha de la actividad.'
    try:
        fecha = datetime.strptime(fecha_cruda, '%Y-%m-%d').date()
    except ValueError:
        return None, 'La fecha no tiene el formato esperado (AAAA-MM-DD).'

    hora_cruda = str(datos.get('hora', '') or '').strip()
    if not hora_cruda:
        return None, 'Falta la hora de la actividad.'
    try:
        hora = datetime.strptime(hora_cruda, '%H:%M').time()
    except ValueError:
        return None, 'La hora no tiene el formato esperado (HH:MM).'

    duracion = str(datos.get('duracion', '') or '').strip() or '2 h'
    if duracion not in dict(SesionServicio.DURACION_CHOICES):
        return None, 'La duracion debe ser 1 h, 2 h o 3 h.'

    # Ojo: en un QueryDict (multipart) .get() devuelve solo el ultimo valor,
    # por eso los convocados se leen con getlist. En JSON llegan como lista.
    if hasattr(datos, 'getlist'):
        ids = datos.getlist('estudiantes')
    else:
        ids = datos.get('estudiantes')
        if ids is None:
            ids = []
        elif isinstance(ids, (str, int)):
            ids = [ids]

    limpios = []
    for valor in ids:
        try:
            limpios.append(int(valor))
        except (TypeError, ValueError):
            continue

    registro = SesionServicio.objects.create(
        id_docente=docente,
        titulo=titulo[:150],
        descripcion=str(datos.get('nota', '') or '').strip() or None,
        taller=taller[:100],
        fecha=fecha,
        hora=hora,
        duracion=duracion,
        estado=SesionServicio.ESTADO_PROGRAMADA,
        evidencia=archivos.get('evidencia') if archivos else None,
    )
    if limpios:
        convocados = Usuario.objects.filter(
            pk__in=limpios, rol=Usuario.ROL_ESTUDIANTE,
        )
        registro.estudiantes.set(convocados)

    return registro, None


@csrf_exempt
@habilita_cors
@require_http_methods(['GET', 'POST', 'OPTIONS'])
def api_sesionservicio_maestro(request):
    """
    Actividades del docente en la tabla `sesionservicio`.

    GET  -> las actividades registradas (mas recientes primero) con sus
            contadores y la evidencia subida.
    POST -> registra una actividad nueva: tematica, taller, fecha, hora,
            duracion, estudiantes convocados y la evidencia (multipart).
            Tambien acepta JSON cuando no hay archivo.
    """

    if request.method == 'OPTIONS':
        # Preflight que dispara el navegador por Content-Type: application/json.
        return HttpResponse(status=204)

    docente = _docente_en_sesion(request)
    if docente is None:
        return _respuesta_sin_sesion()

    if request.method == 'GET':
        return JsonResponse(_datos_sesionservicio(docente))

    if request.content_type and 'application/json' in request.content_type:
        try:
            datos = json.loads(request.body or b'{}')
        except (TypeError, ValueError):
            return JsonResponse(
                {'success': False, 'error': 'El cuerpo de la peticion no es JSON valido.'},
                status=400,
            )
        if not isinstance(datos, dict):
            return JsonResponse(
                {'success': False, 'error': 'El cuerpo debe ser un objeto JSON.'},
                status=400,
            )
        archivos = None
    else:
        datos = request.POST
        archivos = request.FILES

    registro, error = _crear_sesionservicio(docente, datos, archivos)
    if error:
        return JsonResponse({'success': False, 'error': error}, status=400)

    return JsonResponse(
        {
            'success': True,
            'registro': _fila_sesionservicio(registro),
            'stats': _datos_sesionservicio(docente)['stats'],
        },
        status=201,
    )


@csrf_exempt
@habilita_cors
@require_http_methods(['POST', 'OPTIONS'])
def api_sesionservicio_accion(request):
    """
    Marca una actividad registrada como 'Completada' o 'Cancelada'.

    Solo el docente dueno del registro puede tocarlo: un registro ajeno
    responde 403 sin escribir en la base.
    """

    if request.method == 'OPTIONS':
        # Preflight que dispara el navegador por Content-Type: application/json.
        return HttpResponse(status=204)

    docente = _docente_en_sesion(request)
    if docente is None:
        return _respuesta_sin_sesion()

    try:
        datos = json.loads(request.body or b'{}')
    except (TypeError, ValueError):
        return JsonResponse(
            {'success': False, 'error': 'El cuerpo de la peticion no es JSON valido.'},
            status=400,
        )

    if not isinstance(datos, dict):
        return JsonResponse(
            {'success': False, 'error': 'El cuerpo debe ser un objeto JSON.'},
            status=400,
        )

    try:
        id_registro = int(datos.get('id_registro'))
    except (TypeError, ValueError):
        return JsonResponse(
            {'success': False, 'error': 'Falta el id_registro.'},
            status=400,
        )

    accion = str(datos.get('accion', '')).strip().lower()
    if accion not in ('completar', 'cancelar'):
        return JsonResponse(
            {'success': False, 'error': 'accion invalida'},
            status=400,
        )

    registro = SesionServicio.objects.filter(pk=id_registro).first()
    if registro is None:
        return JsonResponse(
            {'success': False, 'error': 'registro no encontrado'},
            status=404,
        )

    if registro.id_docente_id != docente.pk:
        return JsonResponse({'success': False, 'error': 'no autorizado'}, status=403)

    registro.estado = (
        SesionServicio.ESTADO_COMPLETADA
        if accion == 'completar'
        else SesionServicio.ESTADO_CANCELADA
    )
    registro.save(update_fields=['estado'])

    return JsonResponse(
        {
            'success': True,
            'registro': _fila_sesionservicio(registro),
            'stats': _datos_sesionservicio(docente)['stats'],
        },
    )


@csrf_exempt
@habilita_cors
@require_http_methods(['GET', 'OPTIONS'])
def api_dashboard_maestro(request):
    """
    Panel del docente con datos reales: estadisticas, brigadas, asistencias
    que esperan validacion y avisos del encabezado.

    Todo sale del alcance del docente con la sesion abierta; los estados
    vacios son arreglos [], nunca null.
    """

    if request.method == 'OPTIONS':
        # Preflight que dispara el navegador por Content-Type: application/json.
        return HttpResponse(status=204)

    docente = _docente_en_sesion(request)
    if docente is None:
        return _respuesta_sin_sesion()

    return JsonResponse(_datos_panel(docente))


@csrf_exempt
@habilita_cors
@require_http_methods(['POST', 'OPTIONS'])
def api_asistencia_accion(request):
    """
    Valida o rechaza una asistencia desde el panel.

    `aprobar` marca 'Cumplida' con las horas indicadas (4 por defecto,
    acotadas a 0-24); `rechazar` marca 'Inasistencia' y deja las horas en 0.
    Solo el docente de la sesion puede hacerlo: una asistencia ajena
    responde 403 sin tocar la base de datos. La respuesta devuelve los
    mismos contadores que ya recalcula el dashboard.
    """

    if request.method == 'OPTIONS':
        # Preflight que dispara el navegador por Content-Type: application/json.
        return HttpResponse(status=204)

    docente = _docente_en_sesion(request)
    if docente is None:
        return _respuesta_sin_sesion()

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

    try:
        id_registro = int(datos.get('id_registro'))
    except (TypeError, ValueError):
        return JsonResponse(
            {'success': False, 'error': 'Falta el id_registro.'},
            status=400,
        )

    accion = str(datos.get('accion', '')).strip().lower()
    if accion not in ('aprobar', 'rechazar'):
        return JsonResponse(
            {'success': False, 'error': 'accion invalida'},
            status=400,
        )

    try:
        horas = int(datos.get('horas', 4))
    except (TypeError, ValueError):
        return JsonResponse(
            {'success': False, 'error': 'horas invalidas'},
            status=400,
        )
    horas = max(0, min(24, horas))

    registro = (
        Asistencia.objects
        .select_related('id_sesion')
        .filter(pk=id_registro)
        .first()
    )
    if registro is None:
        return JsonResponse(
            {'success': False, 'error': 'registro no encontrado'},
            status=404,
        )

    # Alcance: la sesion de la asistencia tiene que ser del docente en sesion.
    if registro.id_sesion.id_profesor_id != docente.pk:
        return JsonResponse({'success': False, 'error': 'no autorizado'}, status=403)

    if accion == 'aprobar':
        registro.validacion_prof = Asistencia.VALIDACION_CUMPLIDA
        registro.horas_ganadas = horas
    else:
        registro.validacion_prof = Asistencia.VALIDACION_INASISTENCIA
        registro.horas_ganadas = 0
    registro.save(update_fields=['validacion_prof', 'horas_ganadas'])

    return JsonResponse({'success': True, 'stats': _estadisticas_panel(docente)})


@csrf_exempt
@habilita_cors
@require_http_methods(['GET', 'OPTIONS'])
def api_reporte_maestro(request):
    """
    Reporte semanal (ultimos 7 dias) o mensual (ultimos 30) del docente.

    El periodo se aplica a la fecha de confirmacion de la asistencia (con la
    fecha de la sesion como respaldo): `horas_totales` son las horas
    'Cumplida' dentro del periodo, mientras que estudiantes, actividades y
    pendientes describen el alcance completo del docente.
    """

    if request.method == 'OPTIONS':
        # Preflight que dispara el navegador por Content-Type: application/json.
        return HttpResponse(status=204)

    docente = _docente_en_sesion(request)
    if docente is None:
        return _respuesta_sin_sesion()

    tipo = str(request.GET.get('tipo', '')).strip().lower()
    if tipo not in ('semanal', 'mensual'):
        return JsonResponse({'success': False, 'error': 'tipo invalido'}, status=400)

    desde, hasta, inicio, fin = _rango(7 if tipo == 'semanal' else 30)
    en_periodo = _asistencias_en(
        Asistencia.objects.filter(id_sesion__id_profesor=docente), inicio, fin,
    )

    resumen = {
        'estudiantes': docente.estudiantes_a_cargo.count(),
        'actividades': docente.sesiones_dirigidas.values('id_tipo').distinct().count(),
        'horas_totales': _suma_horas(
            en_periodo.filter(validacion_prof=Asistencia.VALIDACION_CUMPLIDA),
        ),
        'pendientes': _pendientes_de(docente).count(),
    }

    actividades = []
    for actividad in _actividades_de(docente):
        base = en_periodo.filter(id_sesion__id_tipo=actividad)
        horas = _suma_horas(
            base.filter(validacion_prof=Asistencia.VALIDACION_CUMPLIDA),
        )
        # La meta es el total de cupos de la brigada, no solo los del periodo.
        meta = sum(
            docente.sesiones_dirigidas.filter(id_tipo=actividad)
            .values_list('cupos_max', flat=True)
        )
        actividades.append({
            'nombre': actividad.nombre_actividad,
            'estudiantes': base.values('id_estudiante').distinct().count(),
            'horas': horas,
            'meta': meta,
            'pct': _porcentaje(horas, meta),
        })

    return JsonResponse({
        'tipo': tipo,
        'periodo': {'desde': desde.isoformat(), 'hasta': hasta.isoformat()},
        'resumen': resumen,
        'actividades': actividades,
    })


# ==========================================================================
# MENSAJES Y CHAT (tabla: mensajes)
# ==========================================================================

# Lista negra del chat. La misma lista vive en el front
# (chat_maestro_horasocial_pro) para avisar mientras se escribe, pero la que
# DECIDE es esta: si el mensaje la trae, la fila nunca se guarda.
PALABRAS_PROHIBIDAS = frozenset([
    'culo', 'culos', 'puta', 'puto', 'putas', 'putos', 'putita', 'putear',
    'puteada', 'puteadas', 'puterio', 'putazo', 'putazos',
    'polla', 'pija', 'pijas', 'pijazo', 'pijazos',
    'verga', 'vergas', 'vergazo', 'vergazos',
    'mierda', 'mierdas', 'cagada', 'cagadas', 'cagar', 'cagado', 'cagon', 'cagona',
    'pendejo', 'pendeja', 'pendejos', 'pendejas', 'pendejada', 'pendejadas',
    'marica', 'maricon', 'maricones', 'mariconada', 'mariconadas',
    'cabron', 'cabrona', 'cabronada', 'cabronadas', 'hijueputa', 'hijueputas',
    'sorete', 'soretes',
    'pelotudo', 'pelotuda', 'pelotudos', 'pelotudez', 'pelotudeces', 'pelotudisimo',
    'boludo', 'boluda', 'boludos', 'boludez', 'boludeces', 'boludisimo',
    'boludazo', 'recontraboludo', 'recontraboluda',
    'choto', 'chota', 'chotos', 'chotas', 'chotear', 'choteada',
    'concha', 'conchas', 'conchudo', 'conchuda',
    'tarado', 'tarada', 'taradez',
    'estupido', 'estupida', 'estupidos', 'estupidez', 'estupideces',
])

# Raices: si un token EMPIEZA con alguna, ya es ofensivo. Es lo que atrapa
# las variantes ("boludito", "pendejito", "puteadita").
RAICES_PROHIBIDAS = (
    'culo', 'put', 'polla', 'pija', 'verga', 'mierd', 'cag',
    'pendej', 'maric', 'cabron', 'hijueputa', 'sorete', 'pelotud',
    'bolud', 'chot', 'conch', 'tarad', 'estupid',
)

# Frases de dos o tres palabras que solas no se ven en el token a token.
FRASES_PROHIBIDAS = (
    'puta madre', 'la puta madre', 'me cago', 'concha de la lora',
    'hijo de mil', 'hijo de puta', 'hija de puta',
    'hijos de puta', 'hijas de puta',
)

# Palabras que EMPIEZAN como una raiz de la lista negra pero no tienen nada
# que ver: pijama empieza con "pija", culombio con "culo", putrefaccion con
# "put". Se comparan exactas, asi que "pijamaputa" sigue cayendo.
PALABRAS_PERMITIDAS = frozenset([
    'pijama', 'pijamas', 'pijao', 'pijaos',
    'culombio', 'culombios',
    'putrefaccion', 'putrefacto', 'putrefacta', 'putrefactos', 'putrefactas',
    'maricultura', 'mariculturas',
])

# Adjuntos: solo imagenes y documentos, con tope de peso.
TAMANO_MAX_ADJUNTO = 5 * 1024 * 1024
EXTENSIONES_IMAGEN = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'}
EXTENSIONES_ARCHIVO = {
    '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.txt', '.csv', '.zip',
}

# Tiempo sin entrar a la plataforma para seguir contando como "en linea".
VENTANA_EN_LINEA = timedelta(minutes=30)


def _normalizar_lenguaje(texto):
    """
    Deja el texto en la forma que se compara: minusculas, sin tildes y con
    los reemplazos tipicos de quien intenta disimular la palabra (0 por o,
    3 por e, 4 por a, 5 y 7 por s, @ por a, $ por s, y la v antes de
    consonante por u).
    """
    sin_tildes = ''.join(
        caracter
        for caracter in unicodedata.normalize('NFD', str(texto).lower())
        if unicodedata.category(caracter) != 'Mn'
    )

    reemplazos = {'0': 'o', '3': 'e', '1': 'i', '4': 'a', '5': 's', '7': 's',
                  '@': 'a', '$': 's'}
    salida = []
    for indice, caracter in enumerate(sin_tildes):
        if caracter in reemplazos:
            salida.append(reemplazos[caracter])
            continue
        if caracter == 'v':
            siguiente = sin_tildes[indice + 1:indice + 2]
            if siguiente and siguiente not in 'aeiou':
                salida.append('u')
                continue
        salida.append(caracter)
    return ''.join(salida)


def _token_limpio(token):
    """El token sin nada que no sea letra: 'p.u.t.a!!' -> 'puta'."""
    return ''.join(
        caracter
        for caracter in _normalizar_lenguaje(token)
        if 'a' <= caracter <= 'z'
    )


def _palabra_prohibida(token):
    """True cuando el token es ofensivo por lista negra o por raiz."""
    limpio = _token_limpio(token)
    if not limpio or limpio in PALABRAS_PERMITIDAS:
        return False
    if limpio in PALABRAS_PROHIBIDAS:
        return True
    return any(limpio.startswith(raiz) for raiz in RAICES_PROHIBIDAS)


def _palabras_ofensivas(texto):
    """
    Devuelve la lista de palabras/frases ofensivas encontradas en el texto.
    Vacia significa que el mensaje se puede enviar.
    """
    encontradas = []
    for token in str(texto).split():
        if _palabra_prohibida(token):
            encontradas.append(token)

    normalizado = ' ' + ' '.join(_normalizar_lenguaje(texto).split()) + ' '
    for frase in FRASES_PROHIBIDAS:
        if frase in normalizado and frase not in encontradas:
            encontradas.append(frase)
    return encontradas


def contiene_lenguaje_prohibido(texto):
    """True cuando el texto trae alguna palabra o frase de la lista negra."""
    return bool(_palabras_ofensivas(texto))


def _tamano_legible(cantidad):
    """'2,4 MB' / '180 KB' / '900 B' para mostrar el peso del adjunto."""
    if cantidad >= 1024 * 1024:
        return f'{cantidad / (1024 * 1024):.1f} MB'.replace('.', ',')
    if cantidad >= 1024:
        return f'{round(cantidad / 1024)} KB'
    return f'{cantidad} B'


def _de_mensaje(remitente):
    """'me' cuando lo mando el docente, 'alum' cuando lo mando el estudiante."""
    return 'me' if remitente == Mensaje.REMITENTE_DOCENTE else 'alum'


def _fila_mensaje(request, mensaje):
    """Una burbuja del chat, con el adjunto ya resuelto a URL absoluta."""
    local = timezone.localtime(mensaje.fecha_hora)
    adjunto = None
    if mensaje.adjunto:
        adjunto = {
            'nombre': mensaje.adjunto_nombre or os.path.basename(mensaje.adjunto.name),
            'tipo': mensaje.adjunto_tipo or Mensaje.ADJUNTO_ARCHIVO,
            'url': request.build_absolute_uri(mensaje.adjunto.url),
            'tamano': _tamano_legible(mensaje.adjunto.size),
            'es_imagen': mensaje.es_imagen,
        }
    return {
        'id': mensaje.id_mensaje,
        'de': _de_mensaje(mensaje.remitente),
        'texto': mensaje.contenido or '',
        'hora': local.strftime('%H:%M'),
        'fecha': local.strftime('%Y-%m-%d'),
        'estado': mensaje.estado,
        'adjunto': adjunto,
    }


def _en_linea(estudiante):
    """Se considera en linea si entro a la plataforma hace menos de 30 min."""
    ultimo = estudiante.last_login
    return bool(ultimo and (timezone.now() - ultimo) <= VENTANA_EN_LINEA)


def _brigada_de(docente, estudiante):
    """La actividad de su ultimo movimiento, igual que en la pantalla de estudiantes."""
    ultima = (
        Asistencia.objects
        .filter(id_estudiante=estudiante, id_sesion__id_profesor=docente)
        .select_related('id_sesion__id_tipo')
        .order_by('-id_sesion__fecha_hora', '-id_registro')
        .first()
    )
    if ultima is None:
        return 'Sin brigada'
    return ultima.id_sesion.id_tipo.nombre_actividad


def _datos_mensajes(request, docente):
    """
    Bandeja del maestro: un hilo por estudiante a cargo con el ultimo
    mensaje, los no leidos y su estado de conexion.

    Los mensajes se traen una sola vez y se agrupan en memoria, asi que el
    listado no crece en consultas con la cantidad de estudiantes.
    """
    estudiantes = list(docente.estudiantes_a_cargo.order_by('nombre_completo'))
    mensajes = Mensaje.objects.filter(id_docente=docente)

    ultimos = {}
    no_leidos = {}
    con_adjunto = 0
    for mensaje in mensajes:
        clave = mensaje.id_estudiante_id
        ultimos[clave] = mensaje
        if mensaje.adjunto:
            con_adjunto += 1
        if (mensaje.remitente == Mensaje.REMITENTE_ESTUDIANTE
                and mensaje.estado == Mensaje.ESTADO_ENVIADO):
            no_leidos[clave] = no_leidos.get(clave, 0) + 1

    conversaciones = []
    for estudiante in estudiantes:
        ultimo = ultimos.get(estudiante.pk)
        local = timezone.localtime(ultimo.fecha_hora) if ultimo else None
        conversaciones.append({
            'id': estudiante.pk,
            'nombre': estudiante.nombre_completo,
            'codigo': estudiante.codigo or f'EST-{estudiante.pk}',
            'grado': estudiante.grado or '',
            'iniciales': _iniciales(estudiante.nombre_completo),
            'brigada': _brigada_de(docente, estudiante),
            'ultimo': (ultimo.contenido or '').strip() if ultimo else '',
            'ultimo_adjunto': (ultimo.adjunto_tipo if ultimo and ultimo.adjunto else ''),
            'ultimo_de': _de_mensaje(ultimo.remitente) if ultimo else '',
            'hora': local.strftime('%H:%M') if local else '',
            'fecha': local.strftime('%Y-%m-%d') if local else '',
            'no_leidos': no_leidos.get(estudiante.pk, 0),
            'en_linea': _en_linea(estudiante),
        })

    # Los hilos con movimiento van primero, del mas nuevo al mas viejo.
    conversaciones.sort(
        key=lambda fila: (fila['fecha'], fila['hora'], fila['nombre']),
        reverse=True,
    )

    return {
        'autenticado': True,
        'docente': {'nombre': docente.nombre_completo},
        'tabla': 'mensajes',
        'stats': {
            'conversaciones': len(conversaciones),
            'con_mensajes': sum(1 for fila in conversaciones if fila['hora']),
            'no_leidos': sum(no_leidos.values()),
            'adjuntos': con_adjunto,
        },
        'conversaciones': conversaciones,
    }


def _datos_chat(request, docente, estudiante):
    """
    La conversacion completa con un estudiante. Al abrirla, los mensajes que
    mando el estudiante pasan a 'Leido' (es el acuse de la bandeja).
    """
    mensajes = Mensaje.objects.filter(id_docente=docente, id_estudiante=estudiante)

    sin_leer = mensajes.filter(
        remitente=Mensaje.REMITENTE_ESTUDIANTE, estado=Mensaje.ESTADO_ENVIADO,
    )
    acusados = sin_leer.count()
    if acusados:
        sin_leer.update(estado=Mensaje.ESTADO_LEIDO)

    return {
        'autenticado': True,
        'docente': {'nombre': docente.nombre_completo},
        'estudiante': {
            'id': estudiante.pk,
            'nombre': estudiante.nombre_completo,
            'codigo': estudiante.codigo or f'EST-{estudiante.pk}',
            'grado': estudiante.grado or '',
            'iniciales': _iniciales(estudiante.nombre_completo),
            'brigada': _brigada_de(docente, estudiante),
            'en_linea': _en_linea(estudiante),
        },
        'mensajes': [_fila_mensaje(request, mensaje) for mensaje in mensajes],
        'leidos_ahora': acusados,
        'limite_adjunto_mb': TAMANO_MAX_ADJUNTO // (1024 * 1024),
    }


def _estudiante_del_docente(docente, valor):
    """
    Resuelve el id de estudiante que llega del chat y comprueba que este a
    cargo del docente en sesion. Devuelve None si no existe o es ajeno.
    """
    try:
        identificador = int(valor)
    except (TypeError, ValueError):
        return None
    return (
        docente.estudiantes_a_cargo
        .filter(pk=identificador)
        .first()
    )


def _adjunto_valido(archivo):
    """
    Revisa peso y extension del adjunto. Devuelve (tipo, error): 'tipo' es
    'imagen' o 'archivo', y 'error' viene con texto cuando no se acepta.
    """
    if archivo is None:
        return '', None

    if archivo.size > TAMANO_MAX_ADJUNTO:
        return '', (
            f'El adjunto pesa mas de {TAMANO_MAX_ADJUNTO // (1024 * 1024)} MB. '
            'Subi una version mas liviana.'
        )

    extension = os.path.splitext(archivo.name or '')[1].lower()
    if extension in EXTENSIONES_IMAGEN:
        return Mensaje.ADJUNTO_IMAGEN, None
    if extension in EXTENSIONES_ARCHIVO:
        return Mensaje.ADJUNTO_ARCHIVO, None
    return '', (
        'Solo se pueden adjuntar imagenes (JPG, PNG, GIF, WEBP, BMP) '
        'o documentos (PDF, Word, Excel, PowerPoint, TXT, CSV, ZIP).'
    )


def _enviar_mensaje(docente, estudiante, datos, archivos):
    """
    Crea el mensaje del docente. Devuelve (mensaje, error, ofensivas) con
    error None cuando salio bien.

    El idioma se revisa ANTES de crear la fila: un mensaje con palabras de
    la lista negra no se guarda y vuelve con el motivo 'lenguaje'.
    """
    contenido = str(datos.get('contenido', '') or '').strip()
    archivo = archivos.get('adjunto') if archivos else None

    if not contenido and archivo is None:
        return None, 'El mensaje esta vacio.', []

    ofensivas = _palabras_ofensivas(contenido) if contenido else []
    if ofensivas:
        return None, (
            'Tu mensaje tiene lenguaje no permitido en el chat. '
            'Reescribilo sin esas palabras para poder enviarlo.'
        ), ofensivas

    tipo_adjunto, error_adjunto = _adjunto_valido(archivo)
    if error_adjunto:
        return None, error_adjunto, []

    mensaje = Mensaje.objects.create(
        id_docente=docente,
        id_estudiante=estudiante,
        remitente=Mensaje.REMITENTE_DOCENTE,
        contenido=contenido,
        adjunto=archivo,
        adjunto_nombre=os.path.basename(archivo.name)[:150] if archivo else '',
        adjunto_tipo=tipo_adjunto,
        estado=Mensaje.ESTADO_ENVIADO,
    )
    return mensaje, None, []


@csrf_exempt
@habilita_cors
@require_http_methods(['GET', 'POST', 'OPTIONS'])
def api_mensajes_maestro(request):
    """
    Bandeja de mensajes del docente.

    GET  -> un hilo por estudiante a cargo, con el ultimo mensaje, los no
            leidos y el estado de conexion.
    POST -> envia un mensaje (multipart con `adjunto`, o JSON sin archivo).
            Si el texto trae lenguaje no permitido responde 400 con
            motivo 'lenguaje' y no guarda nada.
    """

    if request.method == 'OPTIONS':
        # Preflight que dispara el navegador por Content-Type: application/json.
        return HttpResponse(status=204)

    docente = _docente_en_sesion(request)
    if docente is None:
        return _respuesta_sin_sesion()

    if request.method == 'GET':
        return JsonResponse(_datos_mensajes(request, docente))

    if request.content_type and 'multipart/form-data' in request.content_type:
        datos, archivos = request.POST, request.FILES
    else:
        try:
            cuerpo = json.loads(request.body or b'{}')
        except (TypeError, ValueError):
            return JsonResponse(
                {'success': False, 'error': 'El cuerpo de la peticion no es JSON valido.'},
                status=400,
            )
        if not isinstance(cuerpo, dict):
            return JsonResponse(
                {'success': False, 'error': 'El cuerpo debe ser un objeto JSON.'},
                status=400,
            )
        datos, archivos = cuerpo, None

    estudiante = _estudiante_del_docente(docente, datos.get('estudiante'))
    if estudiante is None:
        return JsonResponse(
            {'success': False, 'error': 'estudiante no encontrado'},
            status=404,
        )

    mensaje, error, ofensivas = _enviar_mensaje(docente, estudiante, datos, archivos)
    if error:
        respuesta = {'success': False, 'error': error}
        if ofensivas:
            respuesta['motivo'] = 'lenguaje'
            respuesta['palabras'] = ofensivas
        return JsonResponse(respuesta, status=400)

    return JsonResponse({
        'success': True,
        'mensaje': _fila_mensaje(request, mensaje),
        'estudiante': {
            'id': estudiante.pk,
            'nombre': estudiante.nombre_completo,
        },
    }, status=201)


@csrf_exempt
@habilita_cors
@require_http_methods(['GET', 'OPTIONS'])
def api_chat_maestro(request):
    """
    Conversacion completa con un estudiante a cargo (`?estudiante=<id>`).

    Abrir el chat marca como leidos los mensajes que mando el estudiante, y
    de paso devuelve los datos del contacto para pintar el encabezado.
    """

    if request.method == 'OPTIONS':
        # Preflight que dispara el navegador por Content-Type: application/json.
        return HttpResponse(status=204)

    docente = _docente_en_sesion(request)
    if docente is None:
        return _respuesta_sin_sesion()

    estudiante = _estudiante_del_docente(docente, request.GET.get('estudiante'))
    if estudiante is None:
        return JsonResponse(
            {'success': False, 'error': 'estudiante no encontrado'},
            status=404,
        )

    return JsonResponse(_datos_chat(request, docente, estudiante))
