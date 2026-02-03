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

REM --- Check system Python ---
where py >nul 2>nul
if %errorlevel% neq 0 (
    where python >nul 2>nul
    if %errorlevel% neq 0 goto :python_missing
)
REM ---------------------------

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

echo [Info] Waiting for server to initialize...
set "HealthUrl=http://127.0.0.1:%PORT%/health"
set "MaxRetries=10"

for /L %%i in (1,1,%MaxRetries%) do (
    timeout /t 1 /nobreak >nul
    curl -s -f "%HealthUrl%" >nul
    if not errorlevel 1 goto :server_ready
)

:server_failed
echo.
echo ==============================================================================
echo [ERROR] Server failed to start!
echo ==============================================================================
echo.
echo The server is not responding at %HealthUrl%.
echo Please check if the "Vivagoal Photo Finder" window encountered an error.
echo Common reasons:
echo - Port %PORT% might be in use.
echo - Firewall might be blocking the connection.
echo.
REM Blocking Error Popup
mshta vbscript:Execute("MsgBox ""Server failed to start!"" & vbCrLf & ""Please check the console window for details."", 16, ""Vivagoal Photo Finder"":close")
pause
exit /b 1

:server_ready
echo.
echo [Success] Server is running properly!
echo [Info] Opening browser...
REM Success Popup (Persistent)
mshta vbscript:Execute("MsgBox ""Server is running properly!"" & vbCrLf & ""You can now use the tool in your browser."", 64, ""Vivagoal Photo Finder"":close")
echo.

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

:python_missing
cls
echo ==============================================================================
echo [INFO] Python is not installed.
echo ==============================================================================
echo.
echo I will now download and install Python 3.12 automatically.
echo This may take a few minutes. Please wait...
echo.

REM --- Download Python ---
echo [1/2] Downloading Python 3.12 installer...
curl -L -o python_installer.exe https://www.python.org/ftp/python/3.12.8/python-3.12.8-amd64.exe
if %errorlevel% neq 0 (
    echo [Error] Download failed. Please check your internet connection.
    goto :manual_install_prompt
)

REM --- Install Python ---
echo [2/2] Installing Python... (This happens silently)
echo        Please verify any User Account Control (UAC) prompts if they appear.
start /wait python_installer.exe /quiet InstallAllUsers=0 PrependPath=1 Include_test=0 TargetDir="%LocalAppData%\Programs\Python\Python312"
del python_installer.exe

REM --- Verify Installation ---
set "PY_DIRECT=%LocalAppData%\Programs\Python\Python312\python.exe"
if exist "%PY_DIRECT%" (
    echo [Success] Python installed successfully!
    echo.
    REM Use the direct path for this session since PATH isn't updated yet
    "%PY_DIRECT%" -m venv .venv
    goto :install_deps
)

:manual_install_prompt
echo [Error] Automatic installation failed.
echo.
echo Please install Python manually:
echo 1. Download from https://www.python.org/downloads/
echo 2. Check "Add Python to PATH" during installation.
pause
exit /b 1
