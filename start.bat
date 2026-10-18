@echo off
setlocal
cd /d "%~dp0"
python "%~dp0tools\start_background.py" %*
set "ELYRA_START_EXIT=%ERRORLEVEL%"
if not "%ELYRA_START_EXIT%"=="0" pause
exit /b %ELYRA_START_EXIT%
