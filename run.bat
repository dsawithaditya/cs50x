@echo off
title ClassConnect Server
cd /d "%~dp0"

echo ===================================================
echo               Starting ClassConnect
echo ===================================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo [INFO] Virtual environment not found. Setting it up...
    python -m venv .venv
    call .venv\Scripts\activate.bat
    pip install -r requirements.txt
) else (
    call .venv\Scripts\activate.bat
)

echo [INFO] Server starting at http://127.0.0.1:5000
echo [INFO] Press Ctrl+C in this terminal to stop the server.
echo.

python app.py

pause
