param(
  [string]$Version = "",
  [string]$UpdateDir = ""
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot

function Get-AppVersion {
  $ConfigPath = Join-Path $Root "DESKTOP\automacao_novelis_desktop\config.py"
  $Content = Get-Content -LiteralPath $ConfigPath -Raw
  if ($Content -match 'APP_VERSION\s*=\s*"([^"]+)"') {
    return $Matches[1]
  }
  throw "Nao foi possivel ler APP_VERSION em $ConfigPath"
}

function Get-DefaultUpdateDir {
  $cedilla = [char]0x00C7
  $aTilde = [char]0x00C3
  return "\\192.168.254.250\rede\Publico\AUTOMA$cedilla$aTilde" + "O-CTE\ATUALIZACOES\ATUALIZACAO-NOVELIS"
}

if (-not $Version) {
  $Version = Get-AppVersion
}

if (-not $UpdateDir) {
  $UpdateDir = Get-DefaultUpdateDir
}

powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Root "scripts\build-installer.ps1") -Version $Version

$SetupName = "AutomacaoNovelisSetup-$Version.exe"
$SetupPath = Join-Path $Root "dist\installer\$SetupName"
if (-not (Test-Path $SetupPath)) {
  throw "Setup nao encontrado: $SetupPath"
}

New-Item -ItemType Directory -Force -Path $UpdateDir | Out-Null
Copy-Item -LiteralPath $SetupPath -Destination (Join-Path $UpdateDir $SetupName) -Force

$Manifest = [ordered]@{
  id = "$Version-installer-$(Get-Date -Format 'yyyyMMddHHmmss')"
  version = $Version
  title = "Atualizacao Automacao Novelis $Version"
  notes = "Instalador Inno Setup. Fecha a versao atual, derruba backend/frontend/servico, atualiza atalhos e instala no caminho selecionado."
  installer = $SetupName
  publishedAt = (Get-Date).ToString("s")
}

$Manifest | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $UpdateDir "manifest.json") -Encoding UTF8

Write-Host "Atualizacao publicada em $UpdateDir"
Write-Host "Setup: $SetupName"
