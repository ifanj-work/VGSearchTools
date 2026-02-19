@echo off
setlocal
title VG Photo Search

echo [INFO] Starting VG Photo Search Tools...

if not exist ".venv" (
    echo [ERROR] Virtual environment not found. 
    echo Please run 'setup.bat' first!
    pause
    exit /b 1
)

call .venv\Scripts\activate

REM Launch in background or new window typically, but here we keep it simple conform to start_server.bat
REM Using waitress if available (installed via setup)
if exist ".venv\Scripts\waitress-serve.exe" (
    echo [INFO] Server running with Waitress...
    start "" "http://localhost:5000"
    waitress-serve --listen=127.0.0.1:5000 app:app
) else (
    echo [INFO] Server running with Flask (Dev)...
    start "" "http://localhost:5000"
    python app.py
)

pause
