@echo off
REM ============================================================
REM  HORASOCIAL PRO - Arranque de la DEMO (Modulo Docente)
REM
REM  DOBLE CLIC AQUI el dia de la sustentacion.
REM  Levanta MySQL (Laragon), Django y el servidor web, y abre
REM  el navegador en el login del docente. No hay que tipear nada.
REM ============================================================

title HORASOCIAL PRO - Demo Docente

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0iniciar-demo.ps1"

REM Si algo falla, deja la ventana abierta para leer el mensaje.
if errorlevel 1 (
    echo.
    echo   Hubo un problema al arrancar la demo.
    pause
)
