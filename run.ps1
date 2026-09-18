# ClassConnect Startup Script
$Host.UI.RawUI.WindowTitle = "ClassConnect Server"
Set-Location -Path $PSScriptRoot

Write-Host "===================================================" -ForegroundColor Cyan
Write-Host "               Starting ClassConnect" -ForegroundColor Cyan
Write-Host "===================================================" -ForegroundColor Cyan

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "[INFO] Setting up virtual environment..." -ForegroundColor Yellow
    python -m venv .venv
    .\.venv\Scripts\pip.exe install -r requirements.txt
}

Write-Host "[INFO] Server starting at http://127.0.0.1:5000" -ForegroundColor Green
Write-Host "[INFO] Press Ctrl+C in this terminal to stop the server.`n" -ForegroundColor DarkGray

& ".\.venv\Scripts\python.exe" app.py
