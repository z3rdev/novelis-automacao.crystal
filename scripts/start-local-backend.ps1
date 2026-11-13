param(
    [string]$DatabasePath = '\\192.168.254.250\rede\Publico\novelis-automacao\novelischamado.sqlite',
    [ValidateRange(1,65535)][int]$Port = 8000
)
$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$BackendRoot = Join-Path $ProjectRoot 'BACKEND'
$PythonExe = Join-Path $BackendRoot '.venv\Scripts\python.exe'
$LogDirectory = Join-Path $ProjectRoot 'runtime\logs\backend-local'
New-Item -ItemType Directory -Path $LogDirectory -Force | Out-Null
$LogFile = Join-Path $LogDirectory ('startup-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.log')
$TranscriptStarted = $false
try {
    Start-Transcript -Path $LogFile -Force | Out-Null
    $TranscriptStarted = $true
    Write-Host "Computador: $env:COMPUTERNAME"
    Write-Host "SQLite compartilhado: $DatabasePath"
    Write-Host "Log: $LogFile"
    if (-not (Test-Path -LiteralPath (Split-Path -Parent $DatabasePath) -PathType Container)) {
        throw 'Pasta do SQLite indisponivel. Verifique o acesso ao compartilhamento de rede.'
    }
    if (-not (Test-Path -LiteralPath $PythonExe)) {
        throw 'Python do backend ausente. Execute scripts\bootstrap.ps1 -SkipFrontend neste computador.'
    }
    $Listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if ($Listener) {
        try {
            $Health = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/hub/health/ping" -TimeoutSec 5
        } catch {
            throw "A porta $Port esta ocupada por um backend antigo ou outro programa. Reinicie o backend do projeto para carregar as novas rotas."
        }
        Write-Host "Backend local ja esta ativo. Versao: $($Health.versao)"
        return
    }
    $env:NOVELIS_SQLITE_PATH = $DatabasePath
    $env:API_HOST = '127.0.0.1'
    $env:API_PORT = [string]$Port
    Write-Host "API local: http://127.0.0.1:$Port/api/hub"
    Push-Location -LiteralPath $BackendRoot
    try {
        & $PythonExe -m uvicorn app.main:app --host 127.0.0.1 --port $Port --workers 1 --no-access-log
        if ($LASTEXITCODE -ne 0) { throw 'O backend local encerrou com erro.' }
    } finally { Pop-Location }
} catch {
    Write-Host ("Falha ao iniciar: " + $_.Exception.Message) -ForegroundColor Red
    Write-Host "Consulte o log: $LogFile"
    throw
} finally {
    if ($TranscriptStarted) { Stop-Transcript | Out-Null }
}
