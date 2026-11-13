param(
  [string]$TaskName = "AutomacaoNovelisServico"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$StopFile = Join-Path $Root "runtime\desktop-service.stop"
New-Item -ItemType Directory -Force (Split-Path -Parent $StopFile) | Out-Null
Set-Content -LiteralPath $StopFile -Value "stop" -Encoding UTF8
Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
Write-Host "Servico parado: $TaskName"
