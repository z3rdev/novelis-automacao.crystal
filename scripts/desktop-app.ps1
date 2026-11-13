param()

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$PythonExe = Join-Path $Root "BACKEND\.venv\Scripts\python.exe"
$App = Join-Path $Root "DESKTOP\run_app.py"

if (-not (Test-Path $PythonExe)) {
  Write-Host "Backend nao tem .venv. Rode scripts\bootstrap.ps1 primeiro." -ForegroundColor Yellow
  exit 1
}

& $PythonExe $App
