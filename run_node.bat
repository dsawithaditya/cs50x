@echo off
setlocal
echo ==============================================
echo    ClassConnect (Node.js / Express Server)
echo ==============================================

set "PATH=%USERPROFILE%\.node-bin;%PATH%"

where node >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Node.js executable not found in PATH or %USERPROFILE%\.node-bin.
    pause
    exit /b 1
)

echo Starting Node.js server on http://127.0.0.1:5000 ...
node server.js
pause
