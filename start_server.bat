@echo off
setlocal EnableExtensions

REM Vivagoal Photo Finder quick start (Windows)
REM Usage: start_server.bat [PORT]

set "PORT=%~1"
if "%PORT%"=="" set "PORT=5000"

echo [Info] Starting Vivagoal Photo Finder on port %PORT%
cd /d "%~dp0"

set "PY=.venv\Scripts\python.exe"
set "PIP=.venv\Scripts\pip.exe"
set "WAITRESS=.venv\Scripts\waitress-serve.exe"

if not exist "%PY%" goto :create_venv
goto :install_deps

:create_venv
echo [Info] Creating virtual environment (.venv)...
py -3.12 -m venv .venv >nul 2>nul
if not exist "%PY%" py -3.14 -m venv .venv >nul 2>nul
if not exist "%PY%" python -m venv .venv >nul 2>nul
if not exist "%PY%" goto :venv_error

:install_deps
if exist ".venv\deps_installed.txt" goto :start_server
echo [Info] Installing/upgrading dependencies...
"%PY%" -m pip install -U pip setuptools wheel || goto :pip_error
"%PIP%" install -r requirements.txt || goto :pip_error
echo ok> ".venv\deps_installed.txt"

:start_server
if not exist "%WAITRESS%" goto :waitress_missing
echo [Info] Launching server in background... http://localhost:%PORT%
start "Vivagoal Photo Finder" "%WAITRESS%" --listen=127.0.0.1:%PORT% app:app
timeout /t 2 /nobreak > nul

set "URL=http://localhost:%PORT%/"
where chrome >nul 2>nul
if %errorlevel%==0 goto :open_chrome
start "" "%URL%"
exit /b 0

:open_chrome
start "" chrome "%URL%"
exit /b 0

:waitress_missing
echo [Error] waitress-serve.exe not found. Installation may have failed. Try deleting .venv\deps_installed.txt and rerun.
exit /b 1

:venv_error
echo [Error] Failed to create virtual environment.
exit /b 1

:pip_error
echo [Error] Failed to install Python packages from requirements.txt
exit /b 1
