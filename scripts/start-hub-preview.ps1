param([ValidateRange(1025,65535)][int]$BackendPort = 18036)
$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$HubRoot = Join-Path $ProjectRoot 'FRONTEND-HUB'
$PreviewRoot = Join-Path $ProjectRoot 'runtime\dev-preview'
New-Item -ItemType Directory -Force $PreviewRoot | Out-Null
$Python = Join-Path $ProjectRoot 'BACKEND\.venv\Scripts\python.exe'
if (!(Test-Path -LiteralPath $Python)) { throw 'Python de desenvolvimento nao encontrado.' }
foreach ($PreviewPort in @($BackendPort,1420)) {
    if (Get-NetTCPConnection -LocalPort $PreviewPort -State Listen -ErrorAction SilentlyContinue) {
        throw "A porta $PreviewPort ja esta em uso. Nenhum processo foi encerrado."
    }
}
$VsWhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
$VisualCpp = & $VsWhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
if (!$VisualCpp) { throw 'MSVC x64 e Windows SDK sao necessarios para a janela de desenvolvimento.' }
$DevCmd = Join-Path $VisualCpp 'Common7\Tools\VsDevCmd.bat'
$CompilerEnvironment = & cmd.exe /d /c "call `"$DevCmd`" -no_logo -arch=x64 -host_arch=x64 >nul && set"
if ($LASTEXITCODE -ne 0) { throw 'Falha ao carregar MSVC.' }
foreach ($line in $CompilerEnvironment) {
    if ($line -match '^([^=]+)=(.*)$') { [Environment]::SetEnvironmentVariable($Matches[1], $Matches[2], 'Process') }
}
$env:VITE_API_BASE_URL = "http://127.0.0.1:$BackendPort/api/hub"
$env:VITE_DEFAULT_API_MODE = 'local'
$env:CARGO_BUILD_JOBS = '2'
# The interactive preview runs the same background services as the installed app.
$env:NOVELIS_BACKEND_READINESS = '0'
$env:STORAGE_DIR = Join-Path $PreviewRoot 'backend'
$Config = Join-Path $PreviewRoot 'tauri-preview.json'
@{
    version='0.1.36'; identifier='com.dellmar.novelis-cargo-hub.preview'
    app=@{windows=@(@{label='main';visible=$false;title='Cargo Hub - Previa de desenvolvimento';width=1440;height=900;minWidth=1024;minHeight=700;resizable=$true})
        security=@{csp="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' asset: http://asset.localhost data: blob:; font-src 'self' data:; connect-src 'self' ipc: http://ipc.localhost http://127.0.0.1:$BackendPort http://localhost:$BackendPort ws://127.0.0.1:1420; frame-src 'self' blob: http://127.0.0.1:$BackendPort; object-src 'none'"}}
    bundle=@{active=$false}
} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $Config -Encoding utf8
$Backend = Start-Process -FilePath $Python -ArgumentList @('-m','uvicorn','app.main:app','--host','127.0.0.1','--port',[string]$BackendPort,'--workers','1','--no-access-log') -WorkingDirectory (Join-Path $ProjectRoot 'BACKEND') -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $PreviewRoot 'backend.out.log') -RedirectStandardError (Join-Path $PreviewRoot 'backend.err.log')
@{launcher_pid=$Backend.Id;backend_port=$BackendPort;frontend_port=1420;installer_built=$false} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $PreviewRoot 'processes.json')
Push-Location -LiteralPath $HubRoot
try {
    # tauri dev runs Vite/HMR and a debug executable. It does not build an installer.
    & npx.cmd tauri dev --config $Config
    if ($LASTEXITCODE -ne 0) { throw 'A previa Tauri foi encerrada com erro.' }
} finally {
    Pop-Location
    # Kill only the backend subtree created by this invocation.
    if (!$Backend.HasExited) { & taskkill.exe /PID $Backend.Id /T /F | Out-Null }
}
