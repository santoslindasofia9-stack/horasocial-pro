const express = require('express');
const mysql = require('mysql2');
const path = require('path');
const fs = require('fs');

const app = express();
const PORT = process.env.PORT || 3000;

app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// Never let the browser serve stale HTML from cache (pages change on every deploy).
app.use((req, res, next) => {
    res.setHeader('Cache-Control', 'no-store, no-cache, must-revalidate, proxy-revalidate');
    res.setHeader('Pragma', 'no-cache');
    res.setHeader('Expires', '0');
    next();
});

app.use(express.static(path.join(__dirname), { index: false }));
app.use('/stitch', express.static(path.join(__dirname, 'stitch_horasocial_pro_landing_page')));

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
    
    const createTableQuery = `
        CREATE TABLE IF NOT EXISTS solicitudes_recuperacion (
            id INT AUTO_INCREMENT PRIMARY KEY,
            usuario VARCHAR(50) NOT NULL,
            nombre_completo VARCHAR(150) NOT NULL,
            telefono VARCHAR(20) NOT NULL,
            curso VARCHAR(20) NOT NULL,
            fecha_solicitud TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            estado ENUM('Pendiente', 'Autorizado') DEFAULT 'Pendiente'
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    `;
    db.query(createTableQuery, (tableErr) => {
        if (tableErr) {
            console.error('Error al crear tabla:', tableErr.message);
        } else {
            console.log('Tabla solicitudes_recuperacion OK.');
        }
    });
});

const SOLICITUDES_FILE = path.join(__dirname, 'solicitudes_recuperacion.json');

function getLocalRequests() {
    try {
        if (fs.existsSync(SOLICITUDES_FILE)) {
            const data = fs.readFileSync(SOLICITUDES_FILE, 'utf8');
            return JSON.parse(data || '[]');
        }
    } catch (err) {
        console.error('Error leyendo archivo local:', err.message);
    }
    return [];
}

function saveLocalRequests(requests) {
    try {
        fs.writeFileSync(SOLICITUDES_FILE, JSON.stringify(requests, null, 2), 'utf8');
    } catch (err) {
        console.error('Error escribiendo archivo local:', err.message);
    }
}

app.get('/api/test-db', (req, res) => {
    db.query('SELECT 1 + 1 AS result', (err, results) => {
        if (err) return res.status(500).json({ error: 'Error en la consulta' });
        res.json({ message: 'Base de datos OK', result: results[0].result });
    });
});

app.post('/api/recuperar-contrasena', (req, res) => {
    const { usuario, nombre, telefono, curso } = req.body;
    if (!usuario || !nombre || !telefono || !curso) {
        return res.status(400).json({ error: 'Todos los campos son obligatorios' });
    }

    const dbConnected = db && db.state !== 'disconnected';
    
    const saveRequestToLocal = () => {
        const requests = getLocalRequests();
        const newRequest = {
            id: Date.now(),
            usuario,
            nombre_completo: nombre,
            telefono,
            curso,
            fecha_solicitud: new Date().toISOString(),
            estado: 'Pendiente'
        };
        requests.push(newRequest);
        saveLocalRequests(requests);
        res.json({ success: true, message: 'Solicitud enviada (Modo local)', id: newRequest.id });
    };

    if (dbConnected) {
        const query = 'INSERT INTO solicitudes_recuperacion (usuario, nombre_completo, telefono, curso, estado) VALUES (?, ?, ?, ?, ?)';
        db.query(query, [usuario, nombre, telefono, curso, 'Pendiente'], (err, result) => {
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

app.get('/api/solicitudes-recuperacion', (req, res) => {
    const dbConnected = db && db.state !== 'disconnected';
    if (dbConnected) {
        db.query('SELECT * FROM solicitudes_recuperacion WHERE estado = "Pendiente" ORDER BY fecha_solicitud DESC', (err, results) => {
            if (err) {
                console.error('Error MySQL, recurriendo a local:', err.message);
                res.json(getLocalRequests().filter(r => r.estado === 'Pendiente'));
            } else {
                res.json(results);
            }
        });
    } else {
        res.json(getLocalRequests().filter(r => r.estado === 'Pendiente'));
    }
});

app.post('/api/autorizar-solicitud', (req, res) => {
    const { id, usuario } = req.body;
    if (!id) return res.status(400).json({ error: 'ID requerido' });

    const dbConnected = db && db.state !== 'disconnected';
    
    const updateRequestLocal = () => {
        const requests = getLocalRequests();
        const index = requests.findIndex(r => r.id === parseInt(id) || r.id === id);
        if (index !== -1) {
            requests[index].estado = 'Autorizado';
            saveLocalRequests(requests);
            res.json({ success: true, message: 'Autorizado (local). Contraseña: 123456' });
        } else {
            res.status(404).json({ error: 'Solicitud no encontrada' });
        }
    };

    if (dbConnected) {
        db.query('UPDATE solicitudes_recuperacion SET estado = "Autorizado" WHERE id = ?', [id], (err) => {
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

app.post('/api/rechazar-solicitud', (req, res) => {
    const { id } = req.body;
    if (!id) return res.status(400).json({ error: 'ID requerido' });

    const dbConnected = db && db.state !== 'disconnected';
    
    const deleteRequestLocal = () => {
        let requests = getLocalRequests();
        requests = requests.filter(r => r.id !== parseInt(id) && r.id !== id);
        saveLocalRequests(requests);
        res.json({ success: true, message: 'Solicitud ignorada' });
    };

    if (dbConnected) {
        db.query('DELETE FROM solicitudes_recuperacion WHERE id = ?', [id], (err) => {
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

// Ruta de ingreso desde el login de estudiante: valida que el usuario completó
// el formulario y lo lleva al dashboard. La navegación real POST->redirect
// permite que el navegador ofrezca guardar la contraseña.
app.post('/api/login-estudiante', (req, res) => {
    const { username, password } = req.body;
    if (!username || !password) {
        return res.status(400).json({ error: 'Usuario y contraseña son obligatorios' });
    }
    res.redirect(302, '/estudiante/dashboard');
});

// ==========================================
// RUTAS DE PÁGINAS
// ==========================================

app.get('/', (req, res) => {
    res.sendFile(path.join(__dirname, 'bienvenido_a_horasocial_pro_1', 'code.html'));
});

app.get('/seleccion-rol', (req, res) => {
    res.sendFile(path.join(__dirname, 'selecci_n_de_rol_distribuci_n_expandida_vertical', 'code.html'));
});

app.get('/login', (req, res) => {
    res.sendFile(path.join(__dirname, 'stitch_horasocial_pro_landing_page', 'login_estudiante_distribuci_n_centrada_y_logo_optimizado_2', 'code.html'));
});

app.get('/profesor/login', (req, res) => {
    res.sendFile(path.join(__dirname, 'stitch_horasocial_pro_landing_page', 'login_profesor', 'code.html'));
});

// ✅ RUTA LOGIN ADMINISTRADOR
app.get('/login_administrador', (req, res) => {
    res.sendFile(path.join(__dirname, 'stitch_horasocial_pro_landing_page', 'login_administrador', 'code.html'));
});

app.get('/sobre', (req, res) => {
    res.sendFile(path.join(__dirname, 'stitch_horasocial_pro_landing_page', 'sobre_horasocial_pro_identidad_y_prop_sito', 'code.html'));
});

app.get('/estudiante/dashboard', (req, res) => {
    res.sendFile(path.join(__dirname, 'dashboard_estudiante_horasocial_pro', 'code.html'));
});

app.get('/estudiante/agenda', (req, res) => {
    res.sendFile(path.join(__dirname, 'stitch_horasocial_pro_landing_page', 'agenda_estudiante_junio_2026_premium', 'code.html'));
});

app.get('/estudiante/registro', (req, res) => {
    res.sendFile(path.join(__dirname, 'stitch_horasocial_pro_landing_page', 'registro_de_asistencia_horasocial_pro', 'code.html'));
});

app.get('/estudiante/mensajes', (req, res) => {
    res.sendFile(path.join(__dirname, 'stitch_horasocial_pro_landing_page', 'mis_mensajes_bandeja_de_entrada_estudiante_1', 'code.html'));
});

app.get('/maestro/dashboard', (req, res) => {
    res.sendFile(path.join(__dirname, 'stitch_horasocial_pro_landing_page', 'dashboard_maestro_navegaci_n_y_cierre_de_sesi_n_optimizado', 'code.html'));
});

app.get('/maestro/estudiantes', (req, res) => {
    res.sendFile(path.join(__dirname, 'stitch_horasocial_pro_landing_page', 'gesti_n_estudiantes_perfil_maestro', 'gesti_n_estudiantes_perfil_maestro', 'code.html'));
});

app.get('/maestro/tecnico', (req, res) => {
    res.sendFile(path.join(__dirname, 'stitch_horasocial_pro_landing_page', 'gesti_n_t_cnica_perfil_maestro_2', 'code.html'));
});

app.get('/maestro/mensajes', (req, res) => {
    res.sendFile(path.join(__dirname, 'stitch_horasocial_pro_landing_page', 'mensajes_e_interacci_n_perfil_maestro', 'code.html'));
});

app.get('/admin/dashboard', (req, res) => {
    res.sendFile(path.join(__dirname, 'stitch_horasocial_pro_landing_page', 'dashboard_administrador_control_y_gesti_n_central', 'code.html'));
});

app.get('/admin/docentes', (req, res) => {
    res.sendFile(path.join(__dirname, 'stitch_horasocial_pro_landing_page', 'coordinaci_n_y_ajuste_de_docentes_admin', 'code.html'));
});

app.get('/admin/alertas', (req, res) => {
    res.sendFile(path.join(__dirname, 'stitch_horasocial_pro_landing_page', 'control_de_estudiantes_y_alertas_admin_versi_n_corregida', 'code.html'));
});

// ✅ RUTA /admin/mensajes CORREGIDA - apunta a la carpeta correcta del admin
app.get('/admin/mensajes', (req, res) => {
    res.sendFile(path.join(__dirname, 'stitch_horasocial_pro_landing_page', 'mensajer_a_y_canales_admin_horasocial_pro', 'code.html'));
});

module.exports = app;
// ==========================================
// RUTAS DE PÁGINAS CORREGIDAS PARA VERCEL
// ==========================================

app.get('/', (req, res) => {
    res.sendFile(path.join(__dirname, 'bienvenido_a_horasocial_pro_1', 'code.html'));
});

app.get('/seleccion-rol', (req, res) => {
    res.sendFile(path.join(__dirname, 'selecci_n_de_rol_distribuci_n_expandida_vertical', 'code.html'));
});

app.get('/login', (req, res) => {
    res.sendFile(path.join(__dirname, 'stitch_horasocial_pro_landing_page', 'login_estudiante_distribuci_n_centrada_y_logo_optimizado_2', 'code.html'));
});

app.get('/recuperar-contrasena', (req, res) => {
    res.sendFile(path.join(__dirname, 'stitch_horasocial_pro_landing_page', 'recuperar_contrasena_estudiante', 'code.html'));
});

app.get('/profesor/login', (req, res) => {
    res.sendFile(path.join(__dirname, 'stitch_horasocial_pro_landing_page', 'login_profesor', 'code.html'));
});

app.get('/login_administrador', (req, res) => {
    res.sendFile(path.join(__dirname, 'stitch_horasocial_pro_landing_page', 'login_administrador', 'code.html'));
});

app.get('/sobre', (req, res) => {
    res.sendFile(path.join(__dirname, 'stitch_horasocial_pro_landing_page', 'sobre_horasocial_pro_identidad_y_prop_sito', 'code.html'));
});

app.get('/estudiante/dashboard', (req, res) => {
    res.sendFile(path.join(__dirname, 'dashboard_estudiante_horasocial_pro', 'code.html'));
});

app.get('/estudiante/agenda', (req, res) => {
    res.sendFile(path.join(__dirname, 'stitch_horasocial_pro_landing_page', 'agenda_estudiante_junio_2026_premium', 'code.html'));
});

app.get('/estudiante/registro', (req, res) => {
    res.sendFile(path.join(__dirname, 'stitch_horasocial_pro_landing_page', 'registro_de_asistencia_horasocial_pro', 'code.html'));
});

app.get('/estudiante/mensajes', (req, res) => {
    res.sendFile(path.join(__dirname, 'stitch_horasocial_pro_landing_page', 'mis_mensajes_bandeja_de_entrada_estudiante_1', 'code.html'));
});

app.get('/maestro/dashboard', (req, res) => {
    res.sendFile(path.join(__dirname, 'stitch_horasocial_pro_landing_page', 'dashboard_maestro_navegaci_n_y_cierre_de_sesi_n_optimizado', 'code.html'));
});

app.get('/maestro/estudiantes', (req, res) => {
    res.sendFile(path.join(__dirname, 'stitch_horasocial_pro_landing_page', 'gesti_n_estudiantes_perfil_maestro', 'gesti_n_estudiantes_perfil_maestro', 'code.html'));
});

app.get('/maestro/tecnico', (req, res) => {
    res.sendFile(path.join(__dirname, 'stitch_horasocial_pro_landing_page', 'gesti_n_t_cnica_perfil_maestro_2', 'code.html'));
});

app.get('/maestro/mensajes', (req, res) => {
    res.sendFile(path.join(__dirname, 'stitch_horasocial_pro_landing_page', 'mensajes_e_interacci_n_perfil_maestro', 'code.html'));
});

app.get('/admin/dashboard', (req, res) => {
    res.sendFile(path.join(__dirname, 'stitch_horasocial_pro_landing_page', 'dashboard_administrador_control_y_gesti_n_central', 'code.html'));
});

app.get('/admin/docentes', (req, res) => {
    res.sendFile(path.join(__dirname, 'stitch_horasocial_pro_landing_page', 'coordinaci_n_y_ajuste_de_docentes_admin', 'code.html'));
});

app.get('/admin/alertas', (req, res) => {
    res.sendFile(path.join(__dirname, 'stitch_horasocial_pro_landing_page', 'control_de_estudiantes_y_alertas_admin_versi_n_corregida', 'code.html'));
});

app.get('/admin/mensajes', (req, res) => {
    res.sendFile(path.join(__dirname, 'stitch_horasocial_pro_landing_page', 'mensajer_a_y_canales_admin_horasocial_pro', 'code.html'));
});
if (!process.env.VERCEL) {
    app.listen(PORT, () => {
        console.log(`Servidor corriendo en http://localhost:${PORT}`);
    });
}
