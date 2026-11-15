# Reuse the already validated native development executable for Python/React-only edits.
$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$HubRoot = Join-Path $ProjectRoot 'FRONTEND-HUB'
$PreviewRoot = Join-Path $ProjectRoot 'runtime\dev-preview'
$Native = Join-Path $HubRoot 'src-tauri\target\debug\novelis-cargo-hub.exe'
if (!(Test-Path -LiteralPath $Native)) { throw 'Execute start-hub-preview.ps1 para preparar a janela nativa de desenvolvimento.' }
$NativeTime = (Get-Item -LiteralPath $Native).LastWriteTimeUtc
$NativeInputs = @(Get-ChildItem -LiteralPath (Join-Path $HubRoot 'src-tauri\src') -Filter '*.rs' -File)
$NativeInputs += Get-Item -LiteralPath (Join-Path $HubRoot 'src-tauri\Cargo.toml'),(Join-Path $HubRoot 'src-tauri\tauri.conf.json'),(Join-Path $HubRoot 'src-tauri\capabilities\desktop.json')
if ($NativeInputs | Where-Object LastWriteTimeUtc -GT $NativeTime) { throw 'O codigo nativo mudou. Use start-hub-preview.ps1.' }
foreach ($Port in @(1420,18036)) {
    if (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue) { throw "A porta $Port esta em uso. Nenhum processo foi encerrado." }
}
New-Item -ItemType Directory -Force $PreviewRoot | Out-Null
$env:NOVELIS_BACKEND_READINESS = '0'
$env:STORAGE_DIR = Join-Path $PreviewRoot 'backend'
$env:VITE_API_BASE_URL = 'http://127.0.0.1:18036/api/hub'
$env:VITE_DEFAULT_API_MODE = 'local'
$Python = Join-Path $ProjectRoot 'BACKEND\.venv\Scripts\python.exe'
$Backend = Start-Process -FilePath $Python -ArgumentList @('-m','uvicorn','app.main:app','--host','127.0.0.1','--port','18036','--workers','1','--no-access-log') -WorkingDirectory (Join-Path $ProjectRoot 'BACKEND') -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $PreviewRoot 'backend-v3.out.log') -RedirectStandardError (Join-Path $PreviewRoot 'backend-v3.err.log')
$Vite = Start-Process -FilePath $env:ComSpec -ArgumentList @('/d','/c','npm.cmd run dev:desktop') -WorkingDirectory $HubRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $PreviewRoot 'vite-v3.out.log') -RedirectStandardError (Join-Path $PreviewRoot 'vite-v3.err.log')
try {
    $Ready = $false
    for ($Attempt = 0; $Attempt -lt 90; $Attempt++) {
        try { $null = Invoke-WebRequest -Uri 'http://127.0.0.1:1420/' -UseBasicParsing -TimeoutSec 2; $Ready = $true; break } catch { Start-Sleep -Milliseconds 500 }
        if ($Vite.HasExited) { throw 'Vite nao iniciou. Consulte vite-v3.err.log.' }
    }
    if (!$Ready) { throw 'O servidor de desenvolvimento nao ficou pronto.' }
    $Window = Start-Process -FilePath $Native -WorkingDirectory $HubRoot -PassThru
    @{launcher_pid=$Backend.Id;vite_pid=$Vite.Id;native_pid=$Window.Id;backend_port=18036;frontend_port=1420;installer_built=$false;native_recompiled=$false} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $PreviewRoot 'processes.json')
    $Window.WaitForExit()
} finally {
    # Only helpers created by this invocation; no installed Cargo Hub process is targeted.
    foreach ($Helper in @($Backend,$Vite)) {
        if (!$Helper.HasExited) { & taskkill.exe /PID $Helper.Id /T /F | Out-Null }
    }
}
