// api/mensajes.js
const path = require('path');

module.exports = (req, res) => {
    res.sendFile(path.join(process.cwd(), 'stitch_horasocial_pro_landing_page', 'mensajer_a_y_canales_admin_horasocial_pro', 'code.html'));
};