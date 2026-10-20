<#
    iniciar-demo.ps1
    HORASOCIAL PRO - Modulo Docente

    Levanta todo el entorno de la sustentacion en un solo paso:
      1. Verifica Python, Node y las dependencias.
      2. Arranca Django (backend real, MySQL) en 127.0.0.1:8000.
      3. Arranca server.js (rostro decorado + proxy /api/*) en :3000.
      4. Espera a que ambos respondan y abre el login del docente.

    Uso (desde la raiz del proyecto):
        .\iniciar-demo.ps1

    Si PowerShell bloquea el script, ejecuta una vez:
        Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
        .\iniciar-demo.ps1
#>

$ErrorActionPreference = 'Stop'

# Raiz del proyecto = carpeta donde vive este script.
$Raiz     = $PSScriptRoot
$Backend  = Join-Path $Raiz 'backend'
$VenvPy   = Join-Path $Backend '.venv\Scripts\python.exe'
$DjangoLog = Join-Path $env:TEMP 'horasocial_django.log'
$DjangoErr = Join-Path $env:TEMP 'horasocial_django_err.log'
$NodeLog   = Join-Path $env:TEMP 'horasocial_node.log'
$NodeErr   = Join-Path $env:TEMP 'horasocial_node_err.log'

$PuertoDjango = 8000
$PuertoNode   = 3000

function Escribir($texto, $color = 'Gray') {
    Write-Host $texto -ForegroundColor $color
}

function PuertoEscuchando($puerto) {
    return [bool](Get-NetTCPConnection -LocalPort $puerto -State Listen -ErrorAction SilentlyContinue)
}

function DetenerPuerto($puerto) {
    # Cierra un proceso previo que este ocupando el puerto (una corrida vieja).
    Get-NetTCPConnection -LocalPort $puerto -State Listen -ErrorAction SilentlyContinue |
        ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
}

function EsperarHttp($url, $segundos = 40) {
    # Sondea la URL hasta que responda; devuelve $true si lo logro.
    $fin = (Get-Date).AddSeconds($segundos)
    while ((Get-Date) -lt $fin) {
        try {
            $r = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 4 -ErrorAction Stop
            if ($r.StatusCode -ge 200 -and $r.StatusCode -lt 500) { return $true }
        } catch {
            # El 302 del login no lanza excepcion; los errores de conexion si.
        }
        Start-Sleep -Milliseconds 700
    }
    return $false
}

Escribir ''
Escribir '============================================================' 'Cyan'
Escribir '        HORASOCIAL PRO - Arranque de la DEMO (Docente)'       'Cyan'
Escribir '============================================================' 'Cyan'
Escribir ''

# --------------------------- 1. Requisitos --------------------------------
Escribir '[1/5] Verificando requisitos...' 'Yellow'

if (-not (Test-Path $VenvPy)) {
    Escribir "  X No se encontro el entorno virtual en $VenvPy" 'Red'
    Escribir '    Crea el entorno con: python -m venv backend\.venv' 'Red'
    exit 1
}
$versionDjango = & $VenvPy -c "import django;print(django.get_version())" 2>$null
Escribir "  - Python del venv ......... OK (Django $versionDjango)" 'Green'

$node = Get-Command node -ErrorAction SilentlyContinue
if (-not $node) {
    Escribir '  X No se encontro Node.js en el PATH.' 'Red'
    exit 1
}
Escribir "  - Node.js ................. OK ($(node --version))" 'Green'

if (-not (Test-Path (Join-Path $Raiz 'node_modules\express'))) {
    Escribir '  - Instalando dependencias de Node (npm install)...' 'Yellow'
    Push-Location $Raiz
    npm install --no-audit --no-fund
    Pop-Location
}
Escribir '  - Dependencias de Node .... OK (express)' 'Green'

# Verifica que MySQL/documento responda: un `check` no toca la base, pero
# detecta errores de configuracion antes de arrancar el servidor.
Push-Location $Backend
$check = & $VenvPy manage.py check 2>&1
Pop-Location
if ($LASTEXITCODE -ne 0) {
    Escribir '  X `manage.py check` reporto problemas:' 'Red'
    Escribir $check 'Red'
    exit 1
}
Escribir '  - Configuracion Django .... OK (manage.py check)' 'Green'

# --------------------------- 2. Limpiar puertos ---------------------------
Escribir ''
Escribir '[2/5] Liberando puertos...' 'Yellow'
if (PuertoEscuchando $PuertoDjango) {
    Escribir "  - Cerrando proceso previo en :$PuertoDjango" 'DarkYellow'
    DetenerPuerto $PuertoDjango
}
if (PuertoEscuchando $PuertoNode) {
    Escribir "  - Cerrando proceso previo en :$PuertoNode" 'DarkYellow'
    DetenerPuerto $PuertoNode
}
Start-Sleep -Seconds 2
Escribir '  - Puertos libres .. 8000 y 3000' 'Green'

# --------------------------- 3. Django ------------------------------------
Escribir ''
Escribir '[3/5] Arrancando Django (MySQL, 127.0.0.1:8000)...' 'Yellow'
Start-Process -FilePath $VenvPy `
    -ArgumentList 'manage.py', 'runserver', "127.0.0.1:$PuertoDjango" `
    -WorkingDirectory $Backend `
    -RedirectStandardOutput $DjangoLog `
    -RedirectStandardError  $DjangoErr `
    -WindowStyle Hidden

if (EsperarHttp "http://127.0.0.1:$PuertoDjango/profesor/login") {
    Escribir '  - Django respondiendo ..... OK' 'Green'
} else {
    Escribir '  - X Django no respondio. Revisa el log:' 'Red'
    Escribir "    $DjangoErr" 'Red'
    Get-Content $DjangoErr -Tail 15 -ErrorAction SilentlyContinue | ForEach-Object { Escribir "    $_" 'DarkRed' }
    exit 1
}

# --------------------------- 4. server.js ---------------------------------
Escribir ''
Escribir '[4/5] Arrancando server.js (rostro + proxy, :3000)...' 'Yellow'
Start-Process -FilePath 'node' `
    -ArgumentList 'server.js' `
    -WorkingDirectory $Raiz `
    -RedirectStandardOutput $NodeLog `
    -RedirectStandardError  $NodeErr `
    -WindowStyle Hidden

if (EsperarHttp "http://127.0.0.1:$PuertoNode/api/sesion-actual") {
    Escribir '  - server.js respondiendo ... OK' 'Green'
} else {
    Escribir '  - X server.js no respondio. Revisa el log:' 'Red'
    Escribir "    $NodeErr" 'Red'
    Get-Content $NodeErr -Tail 15 -ErrorAction SilentlyContinue | ForEach-Object { Escribir "    $_" 'DarkRed' }
    exit 1
}

# --------------------------- 5. Abrir navegador ---------------------------
Escribir ''
Escribir '[5/5] Abriendo el login del docente...' 'Yellow'
$urlLogin = "http://127.0.0.1:$PuertoNode/profesor/login"
Start-Process $urlLogin
Escribir "  - Navegador abierto en $urlLogin" 'Green'

# --------------------------- Resumen --------------------------------------
Escribir ''
Escribir '============================================================' 'Cyan'
Escribir '                  DEMO LISTA PARA LA SUSTENTACION'            'Cyan'
Escribir '============================================================' 'Cyan'
Escribir ''
Escribir '  Pagina login ...... ' -NoNewline; Escribir $urlLogin 'White'
Escribir '  Backend (Django) .. ' -NoNewline; Escribir "http://127.0.0.1:$PuertoDjango" 'White'
Escribir ''
Escribir '  CREDENCIALES DEL DOCENTE:' 'Yellow'
Escribir '    Usuario ......... sofia' 'White'
Escribir '    Contrasena ...... sofia2026' 'White'
Escribir ''
Escribir '  OJO: la clave es sofia2026 (en minusculas).' 'DarkYellow'
Escribir ''
Escribir '  Logs (por si algo falla):' 'Gray'
Escribir "    Django : $DjangoErr" 'DarkGray'
Escribir "    Node   : $NodeErr" 'DarkGray'
Escribir ''
Escribir '  Para apagar todo, ejecuta: .\detener-demo.ps1' 'Gray'
Escribir ''
