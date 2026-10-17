# Backend - Modulo de Docentes

Backend en **Django 6.1 + MySQL 8.4** para el modulo de docentes de HORASOCIAL PRO.
Reemplaza el login falso del prototipo `server.js` por autenticacion real contra
la base de datos, con contrasenas cifradas.

---

## Requisitos

| Herramienta | Version | Nota |
| --- | --- | --- |
| Python | 3.14 o superior | Probado con 3.14.4 |
| MySQL | 8.4 | Incluido en Laragon |
| mysqlclient | 2.3.0 | Tiene wheel para Python 3.14, no necesita compilar |

## Instalacion paso a paso

### 1. Entrar a la carpeta del backend

```powershell
cd backend
```

### 2. Crear el entorno virtual

```powershell
python -m venv .venv
```

### 3. Activarlo

```powershell
.venv\Scripts\Activate.ps1
```

Si PowerShell bloquea el script, ejecuta una vez:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

### 4. Instalar las dependencias

```powershell
pip install -r requirements.txt
```

### 5. Crear la base de datos

Con MySQL de Laragon encendido:

```powershell
mysql -h 127.0.0.1 -P 3306 -u root -e "CREATE DATABASE IF NOT EXISTS horas_sociales_docentes CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;"
```

### 6. Crear las tablas

```powershell
python manage.py migrate
```

Esto crea las 15 tablas, incluidas `usuariosa`, `cronograma_sesiones`,
`asistencia_detalle`, `actividades_maestrasa`, `lista_esperaa` y
`solicitudes_recuperacion_maestros`.

### 7. Cargar datos de prueba

```powershell
python manage.py seed_demo
```

### 8. Levantar el servidor

```powershell
python manage.py runserver
```

Abrir: <http://127.0.0.1:8000/>

## Credenciales de prueba

| Rol | Usuario | Contrasena | Entra a |
| --- | --- | --- | --- |
| Directivo | `director@horasocial.local` | `Directivo2026*` | `/admin/` |
| Docente | `docente@horasocial.local` | `Docente2026*` | `/docentes/panel/` |
| Docente (por codigo) | `DOC-0001` | `Docente2026*` | `/docentes/panel/` |
| Estudiante | `estudiante1@horasocial.local` | `Estudiante2026*` | - |

## Rutas

| Metodo | Ruta | Que hace |
| --- | --- | --- |
| GET | `/` | Redirige al login del docente |
| GET/POST | `/docentes/login/` | Inicio de sesion |
| POST | `/docentes/logout/` | Cerrar sesion |
| GET/POST | `/docentes/registro/` | Registrar un docente |
| GET/POST | `/docentes/recuperar/` | Solicitar recuperacion de contrasena |
| GET | `/docentes/panel/` | Panel del docente (requiere sesion) |
| GET/POST | `/docentes/cambiar-contrasena/` | Cambiar la contrasena propia |
| POST | `/api/login-maestro` | Puente con el formulario HTML actual |
| - | `/admin/` | Panel de administracion (directivos) |

## Variables de entorno (opcionales)

La conexion tiene valores por defecto, pero se puede sobreescribir sin tocar el codigo:

| Variable | Valor por defecto |
| --- | --- |
| `DB_NAME` | `horas_sociales_docentes` |
| `DB_USER` | `root` |
| `DB_PASSWORD` | (vacio) |
| `DB_HOST` | `127.0.0.1` |
| `DB_PORT` | `3306` |

Ejemplo:

```powershell
$env:DB_PASSWORD = "mi-clave"; python manage.py runserver
```

## Como funciona el login

1. El formulario envia `identificador` (correo **o** codigo) y `password`.
2. Se busca el usuario por correo o por codigo, sin distinguir mayusculas.
3. Se revisa que la cuenta este activa y no bloqueada.
4. `authenticate()` compara la contrasena contra el hash PBKDF2 guardado en MySQL.
5. Si falla, se suma un intento fallido; a los 5 la cuenta se bloquea.
6. Si acierta, se abre la sesion y se reinicia el contador de intentos.

La contrasena **nunca** se guarda ni se compara en texto plano.

## Problemas frecuentes

### El puerto 3306 lo ocupa otro MySQL

Hay dos MySQL configurados en el puerto 3306 (Laragon y XAMPP). El que arranque
primero se queda con el puerto, y las consultas pueden terminar en el servidor
equivocado. Antes de migrar, confirma cual esta escuchando:

```powershell
Get-Process mysqld | Select-Object Id, Path
```

Si aparece la ruta de Laragon, estas bien. Si aparece la de XAMPP, apaga ese
servicio y vuelve a intentar.

### `Error loading MySQLdb module`

Falta `mysqlclient`. Ejecuta `pip install mysqlclient` con el entorno virtual
activado.

### `(staticfiles.W004) The directory ... does not exist`

Es solo un aviso. La carpeta `backend/static/` existe pero esta vacia; Django la
detecta en cuanto le pongas archivos.

## Notas tecnicas

- `backend/static/` esta reservada para archivos estaticos propios.
- La vista `/api/login-maestro` esta exenta de CSRF para que el formulario HTML
  existente siga funcionando. Lo correcto a futuro es migrar ese HTML al
  formulario de Django y quitar `csrf_exempt`.
