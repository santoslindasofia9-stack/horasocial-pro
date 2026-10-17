# Base de datos `horas_sociales_docentes` — Guía para la sustentación

## 1. La idea en una frase

La base tiene 15 tablas: **6 son el modelo de negocio del proyecto** y **9 son la
infraestructura del framework Django** (sesiones, migraciones, permisos y auditoría).

**No hay tablas basura.** Ninguna de las 9 las escribimos nosotros a mano: las crea y las
usa el motor. Si se eliminan, el sistema deja de arrancar, deja de recordar sesiones y
deja de tener panel de administración.

---

## 2. Las 6 tablas del modelo de negocio

| # | Tabla | Modelo | Clave primaria | Relaciones |
|---|-------|--------|----------------|------------|
| 1 | `usuariosa` | `Usuario` | `id_usuario` | — |
| 2 | `actividades_maestrasa` | `Actividad` | `id_tipo` | — |
| 3 | `cronograma_sesiones` | `Sesion` | `id_sesion` | `id_profesor` → `usuariosa`, `id_tipo` → `actividades_maestrasa` |
| 4 | `asistencia_detalle` | `Asistencia` | `id_registro` | `id_sesion` → `cronograma_sesiones`, `id_estudiante` → `usuariosa` |
| 5 | `lista_esperaa` | `ListaEspera` | `id_espera` | `id_sesion` → `cronograma_sesiones`, `id_estudiante` → `usuariosa` |
| 6 | `solicitudes_recuperacion_maestros` | `SolicitudRecuperacion` | `id` | — (guarda al solicitante como texto) |

### Diagrama de relaciones

```
                    actividades_maestrasa
                          id_tipo (PK)
                              |
                          1:N |  (una actividad tiene muchas sesiones)
                              v
  usuariosa  ----------> cronograma_sesiones <----------+
  id_usuario (PK)  1:N      id_sesion (PK)              |
  rol = Estudiante          id_profesor (FK)            |
      | Profesor            id_tipo (FK)                |
      | Directivo           fecha_hora, cupos, estado   |
      |                         |                        |
      |                     1:N |                        |
      |                         v                        |
      |                   asistencia_detalle        1:N  |
      +-----------------> id_registro (PK)              |
      |  1:N              id_sesion (FK)                 |
      |                   id_estudiante (FK)             |
      |                   validacion_prof                |
      |                   horas_ganadas                  |
      |                                                  |
      +-----------------> lista_esperaa -----------------+
            1:N           id_espera (PK)
                          id_sesion (FK)
                          id_estudiante (FK)

  solicitudes_recuperacion_maestros   (independiente, sin FK)
       id (PK) | usuario (texto) | nombre_completo | telefono | asignatura | estado
```

### Reglas de negocio que viven en el esquema

- **`usuariosa.rol`** distingue los tres tipos de usuario: `Estudiante`, `Profesor`,
  `Directivo`. **Los modelos `Docente` y `Estudiante` son PROXY: no generan tabla
  propia**, son vistas tipadas que filtran por rol.
- **`asistencia_detalle`** tiene una restricción de unicidad `(id_sesion, id_estudiante)`:
  un estudiante no puede registrarse dos veces en la misma sesión.
- **`horas_ganadas`** solo suma al total cuando `validacion_prof = 'Cumplida'`.
- **`usuariosa.intentos_fallidos`** + `estado_cuenta` implementan el bloqueo de cuenta
  a los 5 intentos fallidos.
- Las claves foráneas usan `PROTECT` hacia `usuariosa` y `actividades_maestrasa`:
  no se puede borrar un docente o una actividad que tenga sesiones asociadas.

---

## 3. Las 9 tablas de infraestructura

| Tabla | La crea | Para qué sirve |
|-------|---------|----------------|
| `django_migrations` | marco de migraciones | Registra qué migraciones ya se aplicaron. Sin esta tabla Django no sabe en qué estado está el esquema. |
| `django_session` | `django.contrib.sessions` | Guarda las sesiones activas. La cookie `sessionid` es una clave que apunta acá: es lo que mantiene la sesión abierta entre peticiones. |
| `django_content_type` | `django.contrib.contenttypes` | Registro interno de los modelos instalados. Es la base sobre la que se construyen los permisos. |
| `auth_permission` | `django.contrib.auth` | Una fila por cada permiso posible (modelo + acción). |
| `auth_group` | `django.contrib.auth` | Grupos de permisos. |
| `auth_group_permissions` | `django.contrib.auth` | Tabla intermedia grupo ↔ permiso. |
| `usuariosa_groups` | nuestro modelo, vía `PermissionsMixin` | Tabla intermedia usuario ↔ grupo. |
| `usuariosa_user_permissions` | nuestro modelo, vía `PermissionsMixin` | Tabla intermedia usuario ↔ permiso. |
| `django_admin_log` | `django.contrib.admin` | Auditoría del panel de administración: registra quién cambió qué. |

### Por qué `usuariosa` tiene columnas que no escribimos

`Usuario` hereda de `AbstractBaseUser` y `PermissionsMixin`, así que la tabla
`usuariosa` incluye columnas del motor además de las nuestras:

- del motor: `password`, `last_login`, `is_superuser`, `groups`, `user_permissions`
  (más `is_staff`, `is_active`, `date_joined`, que sí declaramos explícitamente)
- nuestras: `id_usuario`, `nombre_completo`, `correo`, `codigo`, `rol`, `grado`,
  `intentos_fallidos`, `estado_cuenta`

**Esto es una decisión, no un descuido:** delegar el hash de contraseñas a Django
significa PBKDF2-SHA256 con *salt*, nunca texto plano, y control de sesiones probado
por el propio framework.

---

## 4. Preguntas probables del jurado

**"¿Por qué hay 15 tablas si el proyecto tiene 6 entidades?"**
Porque Django añade su propia capa de servicio: sesiones, migraciones, permisos y
auditoría. Son 6 de negocio + 9 del motor.

**"¿Por qué `Docente` y `Estudiante` no tienen tabla propia?"**
Porque los tres roles comparten exactamente la misma mecánica de autenticación
(correo, contraseña, sesión, estado de cuenta). Se modelaron como **modelos proxy**
sobre `usuariosa` con una columna `rol`. Ventaja: no se duplican las columnas de
autenticación y el login es único. Costo reconocido: `grado` (de estudiante) y las
relaciones de docente conviven en una tabla con columnas anulables según el rol.

**"¿Por qué `solicitudes_recuperacion_maestros.usuario` es texto y no una clave foránea?"**
Porque la solicitud la puede enviar alguien que **todavía no puede iniciar sesión**, y
el dato declarado (`codigo` o `correo`) es lo que el docente escribe en el formulario.
Se guarda tal cual para poder contrastarlo después. Es una decisión consciente; el
costo es que si el docente cambia de correo, la solicitud vieja conserva el anterior.

**"¿La contraseña se guarda cifrada?"**
Sí. `make_password` aplica PBKDF2-SHA256 con *salt* en la columna `password` de
`usuariosa`. En la base nunca hay texto plano.

**"¿Cómo se bloquea una cuenta?"**
`intentos_fallidos` se incrementa en cada login fallido; al llegar a 5,
`estado_cuenta` pasa a `Bloqueado` y `tiene_acceso` devuelve falso. Un login correcto
reinicia el contador.

---

## 5. Puntos fuertes para mencionar

1. **Integridad referencial real:** claves foráneas con `PROTECT` y `CASCADE` según la
   regla de negocio, más una restricción de unicidad compuesta en `asistencia_detalle`.
2. **Seguridad delegada, no improvisada:** *hashing* con salt, sesiones gestionadas por
   el framework, protección CSRF en los formularios y CORS restringido al origen del
   frontend.
3. **Correo normalizado a minúsculas** en el modelo y en el gestor, para evitar
   duplicados del tipo `Ana@x` / `ana@x`.
4. **Trazabilidad:** 30 pruebas automatizadas cubren login, registro, recuperación de
   contraseña y los endpoints JSON.
5. **Los datos de negocio son independientes del motor:** las 6 tablas propias no
   dependen de las 9 de infraestructura más allá de la sesión y las migraciones.

---

## 6. Cómo decirlo en 20 segundos

> "La base tiene 15 tablas: 6 son mi modelo de negocio —usuarios, actividades, sesiones,
> asistencias, lista de espera y solicitudes de recuperación— y 9 son la infraestructura
> de Django: sesiones, migraciones, permisos y auditoría. Ninguna de esas 9 la escribí yo
> ni contiene datos míos: las crea y las usa el framework. Eliminarlas no limpiaría el
> diseño, rompería el sistema."
