@echo off
setlocal

REM Vivagoal Photo Finder quick start (Windows)
REM Usage: start_server.bat [PORT]

set "PORT=%~1"
if "%PORT%"=="" set "PORT=5000"

echo [Info] Starting Vivagoal Photo Finder on port %PORT%
cd /d "%~dp0"

REM Create virtual environment if missing
if not exist ".venv" (
  echo [Info] Creating virtual environment (.venv)...
  py -3.12 -m venv .venv 2>nul || py -3.14 -m venv .venv 2>nul || python -m venv .venv
  if not exist ".venv" goto :venv_error
)

call ".\\.venv\\Scripts\\activate.bat" || goto :activate_error

REM Install dependencies once
if not exist ".venv\\deps_installed.txt" (
  echo [Info] Installing/upgrading dependencies...
  python -m pip install -U pip setuptools wheel || goto :pip_error
  pip install -r requirements.txt || goto :pip_error
  echo ok> ".venv\\deps_installed.txt"
) else (
  echo [Info] Dependencies already installed, skipping pip install.
)

set "WAITRESS=.\\.venv\\Scripts\\waitress-serve.exe"
if not exist "%WAITRESS%" goto :waitress_missing

echo [Info] Launching server in background... http://localhost:%PORT%
start "Vivagoal Photo Finder" "%WAITRESS%" --listen=0.0.0.0:%PORT% app:app
timeout /t 2 /nobreak > nul
echo [Info] Opening browser...
start "" "http://localhost:%PORT%/"
exit /b 0

:waitress_missing
echo [Error] waitress-serve.exe not found. Installation may have failed. Try deleting .venv\\deps_installed.txt and rerun.
exit /b 1

:venv_error
echo [Error] Failed to create virtual environment.
exit /b 1

:activate_error
echo [Error] Failed to activate virtual environment.
exit /b 1

:pip_error
echo [Error] Failed to install Python packages from requirements.txt
exit /b 1
