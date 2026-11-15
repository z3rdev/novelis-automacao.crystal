$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$HubRoot = Join-Path $ProjectRoot 'FRONTEND-HUB'
$BackendRoot = Join-Path $ProjectRoot 'BACKEND'
$PreviewRoot = Join-Path $ProjectRoot 'runtime\dev-preview'
$Native = Join-Path $HubRoot 'src-tauri\target\debug\novelis-cargo-hub.exe'
$MainPreview = Get-Process -Name novelis-cargo-hub -ErrorAction SilentlyContinue |
    Where-Object Path -EQ $Native | Select-Object -First 1
if (!$MainPreview) { throw 'Abra primeiro a prévia principal com start-hub-preview.ps1.' }
foreach ($PreviewPort in @(1421,18037)) {
    if (Get-NetTCPConnection -LocalPort $PreviewPort -State Listen -ErrorAction SilentlyContinue) {
        throw "A porta de teste $PreviewPort já está em uso."
    }
}
$Marker = Join-Path $BackendRoot 'CONFIG.dev'
if (!(Test-Path -LiteralPath (Join-Path $BackendRoot 'credentials.json')) -or
    !(Test-Path -LiteralPath $Marker) -or
    !(Select-String -LiteralPath $Marker -Pattern '^\s*DEVMODE\s*=\s*(1|true|on)\s*$' -Quiet)) {
    throw 'O teste Financeiro exige o modo desenvolvedor local.'
}
$env:NOVELIS_PREVIEW_ROLE = 'finance'
$env:NOVELIS_BACKEND_READINESS = '0'
$env:STORAGE_DIR = Join-Path $PreviewRoot 'finance-backend'
New-Item -ItemType Directory -Force -Path $env:STORAGE_DIR | Out-Null
$env:NOVELIS_SQLITE_PATH = Join-Path $env:STORAGE_DIR 'operations.sqlite'
$env:LOGIN_AUDIT_DB_PATH = Join-Path $env:STORAGE_DIR 'logs\sessoes.sqlite'
$env:VITE_API_BASE_URL = 'http://127.0.0.1:1421/api/hub'
$env:VITE_DEFAULT_API_MODE = 'local'
$env:FRONTEND_ORIGIN = 'http://127.0.0.1:1421'
$FinanceChatProfile = Join-Path $PreviewRoot '..\chat-vps\finance-client.private.json'
if (Test-Path -LiteralPath $FinanceChatProfile) { $env:CHAT_SERVER_CONFIG_FILE = (Resolve-Path -LiteralPath $FinanceChatProfile).Path }
$Python = Join-Path $BackendRoot '.venv\Scripts\python.exe'
$Backend = Start-Process -FilePath $Python -ArgumentList @('-m','uvicorn','app.main:app','--host','127.0.0.1','--port','18037','--workers','1','--no-access-log') -WorkingDirectory $BackendRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $PreviewRoot 'finance-backend.out.log') -RedirectStandardError (Join-Path $PreviewRoot 'finance-backend.err.log')
$Vite = Start-Process -FilePath $env:ComSpec -ArgumentList @('/d','/c','npm.cmd run dev:desktop -- --port 1421') -WorkingDirectory $HubRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $PreviewRoot 'finance-vite.out.log') -RedirectStandardError (Join-Path $PreviewRoot 'finance-vite.err.log')
try {
    $Ready = $false
    for ($Attempt = 0; $Attempt -lt 90; $Attempt++) {
        try {
            $null = Invoke-WebRequest 'http://127.0.0.1:1421/' -UseBasicParsing -TimeoutSec 2
            $Identity = Invoke-RestMethod 'http://127.0.0.1:18037/api/hub/session' -TimeoutSec 3
            if ($Identity.identity.windows_user -ne 'PREVIA\financeiro.teste') { throw 'Identidade de teste inválida.' }
            $Ready = $true
            break
        } catch { Start-Sleep -Milliseconds 500 }
        if ($Backend.HasExited -or $Vite.HasExited) { throw 'A prévia Financeiro não iniciou. Consulte finance-backend.err.log e finance-vite.err.log.' }
    }
    if (!$Ready) { throw 'A prévia Financeiro não ficou pronta.' }
    $null = Start-Process -FilePath $Native -ArgumentList '--finance-preview' -WorkingDirectory $HubRoot -PassThru
    @{ backend_launcher=$Backend.Id;vite_launcher=$Vite.Id;main_native=$MainPreview.Id;identity='Financeiro de teste';backend_port=18037;frontend_port=1421;installer_built=$false } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $PreviewRoot 'finance-preview.processes.json')
    $MainPreview.WaitForExit()
} finally {
    foreach ($Helper in @($Backend,$Vite)) {
        if (!$Helper.HasExited) { & taskkill.exe /PID $Helper.Id /T /F | Out-Null }
    }
}
