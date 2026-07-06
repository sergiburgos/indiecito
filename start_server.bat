@echo off
REM Script de inicio estable para Indio-Bot
REM Este script maneja el inicio del servidor de forma más robusta

echo.
echo ============================================
echo   Iniciando Indio-Bot Server
echo ============================================
echo.

REM Detener cualquier proceso uvicorn existente
echo Deteniendo procesos uvicorn anteriores...
taskkill /F /IM uvicorn.exe 2>nul
timeout /t 2 /nobreak >nul

REM Verificar que el archivo .env existe
if not exist ".env" (
    echo ERROR: No se encontro el archivo .env
    echo Por favor, copie .env.example a .env y configure las credenciales
    pause
    exit /b 1
)

REM Iniciar el servidor
echo Iniciando servidor en http://127.0.0.1:8001
echo Presione Ctrl+C para detener el servidor
echo.

uvicorn main:app --host 127.0.0.1 --port 8001

REM Mensaje cuando el servidor se detenga
echo.
echo Servidor detenido. Presione una tecla para cerrar...
pause >nul