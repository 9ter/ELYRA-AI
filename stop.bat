@echo off
rem Stops ELYRA and ngrok HTTP tunnels forwarding to its local port (default 3000).
rem Usage: stop.bat [port]
setlocal
cd /d "%~dp0"
set "ELYRA_STOP_PORT=%~1"
if "%ELYRA_STOP_PORT%"=="" set "ELYRA_STOP_PORT=3000"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0stop.ps1" -Port "%ELYRA_STOP_PORT%"
set "ELYRA_STOP_EXIT=%ERRORLEVEL%"
pause
exit /b %ELYRA_STOP_EXIT%
