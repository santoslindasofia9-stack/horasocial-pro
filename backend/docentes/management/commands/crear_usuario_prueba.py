"""
Comando de gestion: crea (o repara) el usuario de prueba del modulo.

Uso:
    python manage.py crear_usuario_prueba
    python manage.py crear_usuario_prueba --correo otro@x.com --password Otra123

Es idempotente y ademas deja la cuenta lista para iniciar sesion en el
navegador: rol Docente, estado Activo, sin bloqueo y con contrasena cifrada
por Django (PBKDF2-SHA256 + salt). Nunca escribe texto plano en la columna
`password`.

Al terminar verifica el hash con `check_password`, de modo que si el login
fallara despues, el problema no es la credencial sembrada.
"""

from django.core.management.base import BaseCommand

from docentes.models import Usuario

CORREO_POR_DEFECTO = 'docente@horasocial.edu'
CLAVE_POR_DEFECTO = 'Password123'
NOMBRE_POR_DEFECTO = 'Maestro Test'


class Command(BaseCommand):
    help = 'Crea o repara el usuario docente de prueba para ingresar desde el navegador.'

    def add_arguments(self, parser):
        parser.add_argument('--correo', default=CORREO_POR_DEFECTO)
        parser.add_argument('--password', default=CLAVE_POR_DEFECTO)
        parser.add_argument('--nombre', default=NOMBRE_POR_DEFECTO)
        parser.add_argument(
            '--codigo', default='DOC-TEST',
            help='Codigo academico opcional. Cadena vacia para no asignarlo.',
        )
        parser.add_argument('--grado', default='Tecnico')

    def handle(self, *args, **options):
        correo = options['correo'].strip().lower()
        clave = options['password']
        nombre = options['nombre']

        if not correo or not clave:
            self.stderr.write(self.style.ERROR('Correo y contrasena son obligatorios.'))
            return

        usuario = Usuario.objects.filter(correo__iexact=correo).first()
        creado = usuario is None
        if creado:
            usuario = Usuario(correo=correo)

        usuario.nombre_completo = nombre
        usuario.rol = Usuario.ROL_PROFESOR
        usuario.estado_cuenta = Usuario.ESTADO_ACTIVO
        usuario.is_active = True
        usuario.intentos_fallidos = 0
        usuario.grado = options['grado'] or None

        # El codigo es unico: si otro usuario ya lo tiene, no se toca.
        codigo = (options['codigo'] or '').strip() or None
        if codigo:
            en_uso = (
                Usuario.objects.filter(codigo__iexact=codigo)
                .exclude(pk=usuario.pk)
                .exists()
            )
            if en_uso:
                self.stdout.write(
                    self.style.WARNING(
                        f'El codigo "{codigo}" ya pertenece a otro usuario: se omite.'
                    )
                )
                codigo = None
        usuario.codigo = codigo

        # set_password aplica hashing PBKDF2 + salt. No hay texto plano.
        usuario.set_password(clave)
        usuario.save()

        # Verificacion inmediata contra la base de datos.
        usuario.refresh_from_db()
        hash_valido = usuario.check_password(clave)

        self.stdout.write('')
        self.stdout.write(
            self.style.SUCCESS(f'Usuario {"creado" if creado else "actualizado"} correctamente.')
        )
        self.stdout.write(f'  Nombre      : {usuario.nombre_completo}')
        self.stdout.write(f'  Correo      : {usuario.correo}')
        self.stdout.write(f'  Contrasena  : {clave}')
        self.stdout.write(f'  Rol         : {usuario.rol}')
        self.stdout.write(f'  Estado      : {usuario.estado_cuenta}')
        self.stdout.write(f'  id_usuario  : {usuario.pk}')
        self.stdout.write(
            f'  Hash valida : {"SI" if hash_valido else "NO"}'
        )
        if not hash_valido:
            self.stderr.write(
                self.style.ERROR('El hash sembrado NO valida la contrasena. Revisar.')
            )
