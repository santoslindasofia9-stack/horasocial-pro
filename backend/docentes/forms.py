"""
Formularios del modulo de Docentes.

Todas las validaciones de entrada viven aqui: el formulario valida, la vista
decide. Los mensajes de error de credenciales son GENERICOS a proposito, para
no revelar si un correo existe o no en la base de datos.
"""

from django import forms
from django.contrib.auth import password_validation
from django.core.exceptions import ValidationError
from django.db.models import Q

from .models import SolicitudRecuperacion, Usuario

MENSAJE_CREDENCIALES = 'Correo/codigo o contrasena incorrectos.'


def buscar_usuario(identificador):
    """
    Resuelve un usuario por correo electronico O por codigo academico.

    Devuelve None si no existe. La busqueda es case-insensitive para que el
    docente no tenga que recordar mayusculas.
    """
    if not identificador:
        return None
    identificador = identificador.strip()
    return Usuario.objects.filter(
        Q(correo__iexact=identificador) | Q(codigo__iexact=identificador)
    ).first()


class LoginForm(forms.Form):
    """Login real contra MySQL: correo (o codigo) + contrasena."""

    identificador = forms.CharField(
        label='Correo o codigo',
        max_length=100,
        widget=forms.TextInput(attrs={
            'placeholder': 'Correo o codigo',
            'autocomplete': 'username',
            'autofocus': True,
            'class': 'input',
        }),
    )
    password = forms.CharField(
        label='Contrasena',
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Contrasena',
            'autocomplete': 'current-password',
            'class': 'input',
        }),
    )

    def clean(self):
        datos = super().clean()
        identificador = datos.get('identificador')
        password = datos.get('password')

        # Solo resolvemos el usuario; la verificacion del hash la hace
        # authenticate() en la vista (asi respetamos los backends de Django).
        if identificador and password:
            self.usuario = buscar_usuario(identificador)
        return datos

    def get_usuario(self):
        return getattr(self, 'usuario', None)


class RegistroDocenteForm(forms.ModelForm):
    """Registro de un nuevo docente (rol = Profesor)."""

    password1 = forms.CharField(
        label='Contrasena',
        widget=forms.PasswordInput(attrs={'class': 'input', 'autocomplete': 'new-password'}),
        help_text='Minimo 8 caracteres, no puede ser solo numeros.',
    )
    password2 = forms.CharField(
        label='Confirmar contrasena',
        widget=forms.PasswordInput(attrs={'class': 'input', 'autocomplete': 'new-password'}),
    )

    class Meta:
        model = Usuario
        fields = ['nombre_completo', 'correo', 'codigo', 'grado']
        widgets = {
            'nombre_completo': forms.TextInput(attrs={
                'class': 'input', 'placeholder': 'Nombre completo', 'autocomplete': 'name',
            }),
            'correo': forms.EmailInput(attrs={
                'class': 'input', 'placeholder': 'Correo electronico', 'autocomplete': 'email',
            }),
            'codigo': forms.TextInput(attrs={
                'class': 'input', 'placeholder': 'Codigo (opcional)',
            }),
            'grado': forms.TextInput(attrs={
                'class': 'input', 'placeholder': 'Asignatura o grado (opcional)',
            }),
        }

    def clean_correo(self):
        correo = (self.cleaned_data.get('correo') or '').lower().strip()
        if Usuario.objects.filter(correo__iexact=correo).exists():
            raise ValidationError('Ya existe una cuenta registrada con este correo.')
        return correo

    def clean_codigo(self):
        codigo = (self.cleaned_data.get('codigo') or '').strip()
        if not codigo:
            return None
        if Usuario.objects.filter(codigo__iexact=codigo).exists():
            raise ValidationError('Ese codigo ya esta en uso.')
        return codigo

    def clean_password1(self):
        """Aplica los validadores de Django (longitud, comunes, numericas...)."""
        password = self.cleaned_data.get('password1')
        if password:
            usuario_temporal = Usuario(
                correo=self.data.get('correo', ''),
                nombre_completo=self.data.get('nombre_completo', ''),
            )
            password_validation.validate_password(password, usuario_temporal)
        return password

    def clean(self):
        datos = super().clean()
        password1 = datos.get('password1')
        password2 = datos.get('password2')
        if password1 and password2 and password1 != password2:
            self.add_error('password2', 'Las dos contrasenas no coinciden.')
        return datos

    def save(self, commit=True):
        docente = super().save(commit=False)
        docente.rol = Usuario.ROL_PROFESOR
        # set_password() cifra con PBKDF2 + salt. Nunca se guarda texto plano.
        docente.set_password(self.cleaned_data['password1'])
        if commit:
            docente.save()
        return docente


class RecuperarContrasenaForm(forms.ModelForm):
    """
    'Olvide mi contrasena': no cambia la clave, REGISTRA una solicitud que un
    directivo autoriza desde el panel. Es el flujo heredado del modulo.
    """

    class Meta:
        model = SolicitudRecuperacion
        fields = ['usuario', 'nombre_completo', 'telefono', 'asignatura']
        widgets = {
            'usuario': forms.TextInput(attrs={
                'class': 'input', 'placeholder': 'Correo o codigo',
                'autocomplete': 'username',
            }),
            'nombre_completo': forms.TextInput(attrs={
                'class': 'input', 'placeholder': 'Nombre completo', 'autocomplete': 'name',
            }),
            'telefono': forms.TextInput(attrs={
                'class': 'input', 'placeholder': 'Telefono de contacto', 'autocomplete': 'tel',
            }),
            'asignatura': forms.TextInput(attrs={
                'class': 'input', 'placeholder': 'Asignatura que dicta',
            }),
        }
        labels = {
            'usuario': 'Correo o codigo',
            'nombre_completo': 'Nombre completo',
            'telefono': 'Telefono',
            'asignatura': 'Asignatura',
        }

    def clean_telefono(self):
        telefono = (self.cleaned_data.get('telefono') or '').strip()
        digitos = ''.join(caracter for caracter in telefono if caracter.isdigit())
        if len(digitos) < 7:
            raise ValidationError('Ingresa un telefono valido (minimo 7 digitos).')
        return telefono

    def clean_usuario(self):
        """Normaliza el identificador y evita duplicados pendientes."""
        usuario = (self.cleaned_data.get('usuario') or '').strip()
        if SolicitudRecuperacion.objects.filter(
            usuario__iexact=usuario,
            estado=SolicitudRecuperacion.ESTADO_PENDIENTE,
        ).exists():
            raise ValidationError(
                'Ya existe una solicitud pendiente para este usuario. '
                'Espera la autorizacion del directivo.'
            )
        return usuario


class CambiarContrasenaForm(forms.Form):
    """Cambio de contrasena de un docente ya autenticado."""

    password_actual = forms.CharField(
        label='Contrasena actual',
        widget=forms.PasswordInput(attrs={'class': 'input', 'autocomplete': 'current-password'}),
    )
    password_nueva = forms.CharField(
        label='Nueva contrasena',
        widget=forms.PasswordInput(attrs={'class': 'input', 'autocomplete': 'new-password'}),
    )
    password_nueva_confirm = forms.CharField(
        label='Confirmar nueva contrasena',
        widget=forms.PasswordInput(attrs={'class': 'input', 'autocomplete': 'new-password'}),
    )

    def __init__(self, usuario, *args, **kwargs):
        self.usuario = usuario
        super().__init__(*args, **kwargs)

    def clean_password_actual(self):
        actual = self.cleaned_data.get('password_actual')
        if actual and not self.usuario.check_password(actual):
            raise ValidationError('La contrasena actual no es correcta.')
        return actual

    def clean_password_nueva(self):
        nueva = self.cleaned_data.get('password_nueva')
        if nueva:
            password_validation.validate_password(nueva, self.usuario)
        return nueva

    def clean(self):
        datos = super().clean()
        actual = datos.get('password_actual')
        nueva = datos.get('password_nueva')
        confirmacion = datos.get('password_nueva_confirm')

        if nueva and confirmacion and nueva != confirmacion:
            self.add_error('password_nueva_confirm', 'Las contrasenas nuevas no coinciden.')

        if nueva and actual and nueva == actual:
            self.add_error('password_nueva', 'La nueva contrasena debe ser distinta a la actual.')

        return datos

    def save(self):
        # La nueva contrasena tambien pasa por hashing.
        self.usuario.set_password(self.cleaned_data['password_nueva'])
        self.usuario.save(update_fields=['password'])
        return self.usuario
