<#
    detener-demo.ps1
    HORASOCIAL PRO

    Apaga los dos servidores de la demo (Django :8000 y server.js :3000).
    Uso:
        .\detener-demo.ps1
#>

$ErrorActionPreference = 'SilentlyContinue'

function Escribir($texto, $color = 'Gray') {
    Write-Host $texto -ForegroundColor $color
}

Escribir ''
Escribir 'Apagando HORASOCIAL PRO...' 'Yellow'

foreach ($puerto in @(8000, 3000)) {
    $conexiones = Get-NetTCPConnection -LocalPort $puerto -State Listen -ErrorAction SilentlyContinue
    if ($conexiones) {
        $conexiones | ForEach-Object {
            Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
        }
        Escribir "  - Puerto $puerto detenido" 'Green'
    } else {
        Escribir "  - Puerto $puerto ya estaba libre" 'DarkGray'
    }
}

Escribir ''
Escribir 'Demo detenida.' 'Cyan'
Escribir ''
