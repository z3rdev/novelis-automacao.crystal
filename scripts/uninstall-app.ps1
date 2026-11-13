param(
  [string]$TaskName = "AutomacaoNovelisServico"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$ShortcutPath = Join-Path ([Environment]::GetFolderPath("Desktop")) "Automacao Novelis.lnk"

powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Root "scripts\remove-desktop-service.ps1") -TaskName $TaskName
Remove-Item -LiteralPath $ShortcutPath -Force -ErrorAction SilentlyContinue

Write-Host "Atalho removido. Dependencias locais foram mantidas para preservar o ambiente."
