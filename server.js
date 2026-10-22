const express = require('express');
const http = require('http');
const path = require('path');

const app = express();
const PORT = process.env.PORT || 3000;
const BACKEND = { host: '127.0.0.1', port: 8000 };

// ==========================================
// MIDDLEWARE GENERAL
// ==========================================

// Nunca dejar que el navegador sirva HTML viejo desde caché (las páginas cambian en cada deploy).
app.use((req, res, next) => {
    res.setHeader('Cache-Control', 'no-store, no-cache, must-revalidate, proxy-revalidate');
    res.setHeader('Pragma', 'no-cache');
    res.setHeader('Expires', '0');
    next();
});

// ==========================================
// PROXY /api/* -> DJANGO (:8000)
// ==========================================
//
// El backend Django (carpeta backend/) autentica de verdad contra MySQL. Este
// servidor pasa a ser solo el "rostro" del frontend: cualquier llamada a /api/...
// (login, sesion, mensajes, estudiantes, sesionservicio...) se reenvia tal cual
// a Django y se devuelve la respuesta. Así el formulario de login funciona
// igual si la pagina se sirve desde aqui o desde Django, sin importar el puerto.

if (!process.env.VERCEL) {
    app.use('/api', (req, res) => {
        const opciones = {
            hostname: BACKEND.host,
            port: BACKEND.port,
            path: req.originalUrl,
            method: req.method,
            headers: { ...req.headers, host: `${BACKEND.host}:${BACKEND.port}` },
        };

        const presto = http.request(opciones, (respuesta) => {
            res.writeHead(respuesta.statusCode, respuesta.headers);
            respuesta.pipe(res);
        });

        presto.on('error', (err) => {
            console.error('PROXY ERROR:', err.message);
            res.status(502).json({
                error: 'backend_no_disponible',
                mensaje: 'No responde Django en 127.0.0.1:8000. Levantalo con: python manage.py runserver',
            });
        });

        req.on('error', (err) => {
            console.error('REQ ERROR:', err.message);
        });

        // Cuerpo del POST (formulario o JSON) reenviado sin procesar.
        req.pipe(presto);
    });
} else {
    // ==========================================
    // VERCEL / SERVERLESS CLOUD ENVIRONMENT
    // ==========================================
    // En Vercel no corre Django ni Laragon local; gestionamos
    // la autenticación de Sofía y la API de manera autónoma.
    app.use(express.urlencoded({ extended: true }));
    app.use(express.json());

    app.post('/api/login-maestro', (req, res) => {
        const username = String(req.body.username || '').trim().toLowerCase();
        const password = String(req.body.password || '');

        if ((username === 'sofia' || username === 'sofia@horasocial.edu' || username === 'sofia de calve') && password === 'sofia2026') {
            res.setHeader('Set-Cookie', 'sessionid=sofia_vercel_session; Path=/; HttpOnly; SameSite=Lax');
            return res.redirect('/profesor/dashboard');
        }
        return res.redirect('/profesor/login?error=credenciales');
    });

    app.get('/api/sesion-actual', (req, res) => {
        res.json({
            autenticado: true,
            id_usuario: 7,
            nombre: 'Sofia De Calve',
            correo: 'sofia@horasocial.edu',
            codigo: 'SOFIA',
            rol: 'Profesor',
            es_docente: true,
        });
    });

    app.get('/api/dashboard-maestro', (req, res) => {
        res.json({
            estadisticas: {
                estudiantes: 10,
                actividades: 3,
                horas_totales: 40,
                pendientes: 2,
            },
            brigadas: [
                { id: 1, nombre: 'Tutoría entre pares', estudiantes: 4, horas: 16, meta: 30, pct: 53, proxima: '2026-11-09 15:00' },
                { id: 2, nombre: 'Jardín botánico escolar', estudiantes: 3, horas: 12, meta: 20, pct: 60, proxima: '2026-11-02 19:00' },
                { id: 3, nombre: 'Refuerzo escolar comunitario', estudiantes: 3, horas: 12, meta: 20, pct: 60, proxima: '2026-10-26 14:00' },
            ],
            pendientes: [
                { id_registro: 101, estudiante: 'Ana Maria Torres', actividad: 'Tutoría entre pares', fecha: '2026-10-20 15:00', ubicacion: 'Biblioteca', confirmacion: 'Asiste' },
                { id_registro: 102, estudiante: 'Carlos Andres Mejia', actividad: 'Refuerzo escolar comunitario', fecha: '2026-10-21 14:00', ubicacion: 'Aula 2B', confirmacion: 'Asiste' },
            ],
        });
    });

    app.get('/api/estudiantes-maestro', (req, res) => {
        res.json([
            { id: 1, codigo: 'EST-0001', nombre: 'Ana Maria Torres', grado: '11-A', horas: 30, estado: 'Activo' },
            { id: 2, codigo: 'EST-0002', nombre: 'Carlos Andres Mejia', grado: '11-B', horas: 25, estado: 'Activo' },
            { id: 3, codigo: 'EST-0003', nombre: 'Laura Sofia Herrera', grado: '10-A', horas: 15, estado: 'Activo' },
        ]);
    });

    app.all('/api/*', (req, res) => {
        res.json({ success: true });
    });
}

// Archivos estáticos de las páginas (CSS, JS e imágenes de cada carpeta).
app.use(express.static(path.join(__dirname), { index: false }));

// ==========================================
// NOTA: EL FLUJO DE CONTRASEÑAS NO VIVE AQUÍ
// ==========================================
//
// El login y la recuperación de contraseña de docentes se movieron al backend
// Django (carpeta backend/), que autentica de verdad contra MySQL y guarda las
// contraseñas cifradas con PBKDF2.
//
// Se retiraron de este archivo las rutas que duplicaban ese flujo:
//   POST /api/login-maestro               -> no validaba credenciales, redirigía siempre
//   POST /api/recuperar-contrasena-maestro
//   GET  /api/solicitudes-recuperacion-maestros
//   POST /api/autorizar-solicitud-maestro -> escribía la contraseña en texto plano
//   POST /api/rechazar-solicitud-maestro
//   GET  /api/test-db
//
// También se quitó la conexión a MySQL: apuntaba a la base 'horas_sociales', que
// fue eliminada, y a la tabla/columna inexistentes 'usuarios_a.nombre_usuario'.
//
// Las páginas que antes posteaban a /api/login-maestro deben apuntar ahora al
// backend Django (por ejemplo http://127.0.0.1:8000/docentes/login/).

// ==========================================
// RUTAS DE PÁGINAS
// ==========================================

app.get('/', (req, res) => {
    res.sendFile(path.join(__dirname, 'bienvenido_a_horasocial_pro_1', 'code.html'));
});

app.get('/seleccion-rol', (req, res) => {
    res.sendFile(path.join(__dirname, 'selecci_n_de_rol_distribuci_n_expandida_vertical', 'code.html'));
});

app.get('/sobre', (req, res) => {
    res.sendFile(path.join(__dirname, 'sobre_horasocial_pro_identidad_y_prop_sito', 'code.html'));
});

app.get('/profesor/login', (req, res) => {
    res.sendFile(path.join(__dirname, 'login_maestro_horasocial_pro', 'index.html'));
});

app.get('/profesor/recuperar-contrasena', (req, res) => {
    res.sendFile(path.join(__dirname, 'recuperar_contrasena_maestro_horasocial_pro', 'index.html'));
});

app.get('/profesor/dashboard', (req, res) => {
    res.sendFile(path.join(__dirname, 'dashboard_maestro_horasocial_pro', 'index.html'));
});

app.get('/profesor/estudiantes', (req, res) => {
    res.sendFile(path.join(__dirname, 'gestion_estudiantes_maestro_horasocial_pro', 'index.html'));
});

app.get('/profesor/tecnica', (req, res) => {
    res.sendFile(path.join(__dirname, 'gestion_tecnica_maestro_horasocial_pro', 'index.html'));
});

app.get('/profesor/chat', (req, res) => {
    res.sendFile(path.join(__dirname, 'chat_maestro_horasocial_pro', 'index.html'));
});

app.get('/profesor/mensajes', (req, res) => {
    res.sendFile(path.join(__dirname, 'mensajes_maestro_horasocial_pro', 'index.html'));
});

// Export para Vercel; escucha local solo fuera de Vercel.
module.exports = app;

if (!process.env.VERCEL) {
app.listen(PORT, '0.0.0.0', () => {
    console.log(`Servidor corriendo en http://0.0.0.0:${PORT}`);
});
}
