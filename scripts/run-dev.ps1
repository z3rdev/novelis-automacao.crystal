param(
  [int]$BackendPort = 8000,
  [int]$FrontendPort = 5173
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$BackendDir = Join-Path $Root "BACKEND"
$FrontendDir = Join-Path $Root "FRONTEND"
$FrontendDistDir = Join-Path $FrontendDir "dist"
$RuntimeDir = Join-Path $Root "runtime"
$PythonExe = Join-Path $BackendDir ".venv\Scripts\python.exe"
$InstallMarker = Join-Path $Root ".automacao-novelis-install"

New-Item -ItemType Directory -Force $RuntimeDir | Out-Null

powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Root "scripts\bootstrap.ps1") -SkipFrontend
if ($LASTEXITCODE -ne 0) {
  throw "Preparacao do backend falhou. Consulte $RuntimeDir\bootstrap-result.json e $RuntimeDir\bootstrap.log"
}
if (-not (Test-Path $PythonExe)) {
  throw "Backend nao tem Python local/.venv apos bootstrap: $PythonExe"
}

$BackendLog = Join-Path $RuntimeDir "backend-dev.log"
$FrontendLog = Join-Path $RuntimeDir "frontend-dev.log"

function Test-PortListening {
  param([int]$Port)
  $connection = Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
  return $null -ne $connection
}

if (-not (Test-PortListening $BackendPort)) {
  # Uvicorn --reload usa SelectorEventLoop no Windows, que quebra subprocessos do Playwright.
  $BackendCommand = "cd /d `"$BackendDir`" && `"$PythonExe`" -m uvicorn app.main:app --host 127.0.0.1 --port $BackendPort --no-access-log > `"$BackendLog`" 2>&1"
  Start-Process -WindowStyle Hidden -FilePath "cmd.exe" -ArgumentList "/d", "/c", $BackendCommand
  Start-Sleep -Seconds 2
} else {
  Write-Host "Backend ja esta rodando na porta $BackendPort."
}

if (-not (Test-PortListening $FrontendPort)) {
  $UseStaticFrontend = (Test-Path $InstallMarker) -or (-not (Test-Path (Join-Path $FrontendDir "node_modules")))
  if ($UseStaticFrontend -and (Test-Path (Join-Path $FrontendDistDir "index.html"))) {
    $FrontendCommand = "cd /d `"$FrontendDistDir`" && `"$PythonExe`" -m http.server $FrontendPort --bind 127.0.0.1 > `"$FrontendLog`" 2>&1"
  } else {
    if (-not (Test-Path (Join-Path $FrontendDir "node_modules"))) {
      powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Root "scripts\bootstrap.ps1") -SkipBackend
    }
    $FrontendCommand = "cd /d `"$FrontendDir`" && npm run dev -- --port $FrontendPort > `"$FrontendLog`" 2>&1"
  }
  Start-Process -WindowStyle Hidden -FilePath "cmd.exe" -ArgumentList "/d", "/c", $FrontendCommand
  Start-Sleep -Seconds 2
} else {
  Write-Host "Frontend ja esta rodando na porta $FrontendPort."
}

Write-Host "Backend:  http://127.0.0.1:$BackendPort"
Write-Host "Frontend: http://127.0.0.1:$FrontendPort"
Write-Host "Logs:     $RuntimeDir"
