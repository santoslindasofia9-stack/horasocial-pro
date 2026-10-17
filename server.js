const express = require('express');
const mysql = require('mysql2');
const path = require('path');
const fs = require('fs');

const app = express();
const PORT = process.env.PORT || 3000;

// ==========================================
// MIDDLEWARE GENERAL
// ==========================================

app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// Nunca dejar que el navegador sirva HTML viejo desde caché (las páginas cambian en cada deploy).
app.use((req, res, next) => {
    res.setHeader('Cache-Control', 'no-store, no-cache, must-revalidate, proxy-revalidate');
    res.setHeader('Pragma', 'no-cache');
    res.setHeader('Expires', '0');
    next();
});

// Archivos estáticos de las páginas (CSS, JS e imágenes de cada carpeta).
app.use(express.static(path.join(__dirname), { index: false }));

// ==========================================
// CONEXIÓN A MYSQL (módulo docente)
// ==========================================

const db = mysql.createConnection({
    host: 'localhost',
    user: 'root',
    password: '',
    database: 'horas_sociales'
});

db.connect((err) => {
    if (err) {
        console.error('Error al conectar a MySQL:', err.message);
        console.log('Asegúrate de tener XAMPP encendido con MySQL en verde.');
        return;
    }
    console.log('Conexión exitosa a MySQL.');

    const createMaestrosTableQuery = `
        CREATE TABLE IF NOT EXISTS solicitudes_recuperacion_maestros (
            id INT AUTO_INCREMENT PRIMARY KEY,
            usuario VARCHAR(50) NOT NULL,
            nombre_completo VARCHAR(150) NOT NULL,
            telefono VARCHAR(20) NOT NULL,
            asignatura VARCHAR(100) NOT NULL,
            fecha_solicitud TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            estado ENUM('Pendiente', 'Autorizado') DEFAULT 'Pendiente'
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    `;
    db.query(createMaestrosTableQuery, (tableErr) => {
        if (tableErr) {
            console.error('Error al crear tabla maestros:', tableErr.message);
        } else {
            console.log('Tabla solicitudes_recuperacion_maestros OK.');
        }
    });
});

// ==========================================
// RESPALDO LOCAL EN JSON (solo docentes)
// Se usa cuando MySQL no está disponible.
// ==========================================

const SOLICITUDES_MAESTROS_FILE = path.join(__dirname, 'solicitudes_recuperacion_maestros.json');

function getLocalMaestroRequests() {
    try {
        if (fs.existsSync(SOLICITUDES_MAESTROS_FILE)) {
            const data = fs.readFileSync(SOLICITUDES_MAESTROS_FILE, 'utf8');
            return JSON.parse(data || '[]');
        }
    } catch (err) {
        console.error('Error leyendo archivo local maestros:', err.message);
    }
    return [];
}

function saveLocalMaestroRequests(requests) {
    try {
        fs.writeFileSync(SOLICITUDES_MAESTROS_FILE, JSON.stringify(requests, null, 2), 'utf8');
    } catch (err) {
        console.error('Error escribiendo archivo local maestros:', err.message);
    }
}

// ==========================================
// API - MÓDULO DOCENTE
// ==========================================

app.get('/api/test-db', (req, res) => {
    db.query('SELECT 1 + 1 AS result', (err, results) => {
        if (err) return res.status(500).json({ error: 'Error en la consulta' });
        res.json({ message: 'Base de datos OK', result: results[0].result });
    });
});

// Solicitud de recuperación de contraseña de docente.
app.post('/api/recuperar-contrasena-maestro', (req, res) => {
    const { usuario, nombre, telefono, asignatura } = req.body;
    if (!usuario || !nombre || !telefono || !asignatura) {
        return res.status(400).json({ error: 'Todos los campos son obligatorios' });
    }

    const dbConnected = db && db.state !== 'disconnected';
    
    const saveRequestToLocal = () => {
        const requests = getLocalMaestroRequests();
        const newRequest = {
            id: Date.now(),
            usuario,
            nombre_completo: nombre,
            telefono,
            asignatura,
            fecha_solicitud: new Date().toISOString(),
            estado: 'Pendiente'
        };
        requests.push(newRequest);
        saveLocalMaestroRequests(requests);
        res.json({ success: true, message: 'Solicitud enviada (Modo local)', id: newRequest.id });
    };

    if (dbConnected) {
        const query = 'INSERT INTO solicitudes_recuperacion_maestros (usuario, nombre_completo, telefono, asignatura, estado) VALUES (?, ?, ?, ?, ?)';
        db.query(query, [usuario, nombre, telefono, asignatura, 'Pendiente'], (err, result) => {
            if (err) {
                console.error('Error MySQL, recurriendo a local:', err.message);
                saveRequestToLocal();
            } else {
                res.json({ success: true, message: 'Solicitud enviada', id: result.insertId });
            }
        });
    } else {
        saveRequestToLocal();
    }
});

// Listado de solicitudes pendientes de docentes.
app.get('/api/solicitudes-recuperacion-maestros', (req, res) => {
    const dbConnected = db && db.state !== 'disconnected';
    if (dbConnected) {
        db.query('SELECT * FROM solicitudes_recuperacion_maestros WHERE estado = "Pendiente" ORDER BY fecha_solicitud DESC', (err, results) => {
            if (err) {
                console.error('Error MySQL, recurriendo a local:', err.message);
                res.json(getLocalMaestroRequests().filter(r => r.estado === 'Pendiente'));
            } else {
                res.json(results);
            }
        });
    } else {
        res.json(getLocalMaestroRequests().filter(r => r.estado === 'Pendiente'));
    }
});

// Autoriza una solicitud de docente y restablece su contraseña.
app.post('/api/autorizar-solicitud-maestro', (req, res) => {
    const { id, usuario } = req.body;
    if (!id) return res.status(400).json({ error: 'ID requerido' });

    const dbConnected = db && db.state !== 'disconnected';
    
    const updateRequestLocal = () => {
        const requests = getLocalMaestroRequests();
        const index = requests.findIndex(r => r.id === parseInt(id) || r.id === id);
        if (index !== -1) {
            requests[index].estado = 'Autorizado';
            saveLocalMaestroRequests(requests);
            res.json({ success: true, message: 'Autorizado (local). Contraseña: 123456' });
        } else {
            res.status(404).json({ error: 'Solicitud no encontrada' });
        }
    };

    if (dbConnected) {
        db.query('UPDATE solicitudes_recuperacion_maestros SET estado = "Autorizado" WHERE id = ?', [id], (err) => {
            if (err) {
                console.error('Error MySQL, recurriendo a local:', err.message);
                updateRequestLocal();
            } else {
                if (usuario) {
                    db.query('UPDATE usuarios_a SET password = ? WHERE nombre_usuario = ?', ['123456', usuario], (userErr) => {
                        if (userErr) console.error('Error actualizando contraseña:', userErr.message);
                        else console.log(`Contraseña de ${usuario} restablecida a "123456"`);
                    });
                }
                res.json({ success: true, message: 'Autorizado. Contraseña: 123456' });
            }
        });
    } else {
        updateRequestLocal();
    }
});

// Descarta una solicitud de docente.
app.post('/api/rechazar-solicitud-maestro', (req, res) => {
    const { id } = req.body;
    if (!id) return res.status(400).json({ error: 'ID requerido' });

    const dbConnected = db && db.state !== 'disconnected';
    
    const deleteRequestLocal = () => {
        let requests = getLocalMaestroRequests();
        requests = requests.filter(r => r.id !== parseInt(id) && r.id !== id);
        saveLocalMaestroRequests(requests);
        res.json({ success: true, message: 'Solicitud ignorada' });
    };

    if (dbConnected) {
        db.query('DELETE FROM solicitudes_recuperacion_maestros WHERE id = ?', [id], (err) => {
            if (err) {
                console.error('Error MySQL, recurriendo a local:', err.message);
                deleteRequestLocal();
            } else {
                res.json({ success: true, message: 'Solicitud ignorada' });
            }
        });
    } else {
        deleteRequestLocal();
    }
});

// Login de profesor: la navegación POST->redirect permite que el navegador
// ofrezca guardar la contraseña.
app.post('/api/login-maestro', (req, res) => {
    const { username, password } = req.body;
    if (!username || !password) {
        return res.status(400).json({ error: 'Usuario y contraseña son obligatorios' });
    }
    res.redirect(302, '/profesor/dashboard');
});

// ==========================================
// RUTAS DE PÁGINAS (módulo docente)
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
    app.listen(PORT, () => {
        console.log(`Servidor corriendo en http://localhost:${PORT}`);
    });
}
