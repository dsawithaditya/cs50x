Write-Host "==============================================" -ForegroundColor Cyan
Write-Host "   ClassConnect (Node.js / Express Server)    " -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan

$nodePath = "$env:USERPROFILE\.node-bin"
if (Test-Path $nodePath) {
    $env:PATH = "$nodePath;$env:PATH"
}

if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Write-Host "[ERROR] Node.js is not found in PATH." -ForegroundColor Red
    pause
    exit 1
}

Write-Host "Starting ClassConnect on http://127.0.0.1:5000 ..." -ForegroundColor Green
node server.js
