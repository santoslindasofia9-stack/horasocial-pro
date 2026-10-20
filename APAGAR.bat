@echo off
REM ============================================================
REM  HORASOCIAL PRO - Apagar la DEMO
REM  DOBLE CLIC AQUI para detener Django y el servidor web.
REM ============================================================

title HORASOCIAL PRO - Apagar Demo

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0detener-demo.ps1"

echo.
pause
