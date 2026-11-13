param(
  [string]$TaskName = "AutomacaoNovelisServico"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Remove-Item -LiteralPath (Join-Path $Root "runtime\desktop-service.stop") -Force -ErrorAction SilentlyContinue
Start-ScheduledTask -TaskName $TaskName
Write-Host "Servico iniciado: $TaskName"
