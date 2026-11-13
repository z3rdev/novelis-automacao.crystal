param(
  [string]$Version = "",
  [ValidateSet('development','distribution')][string]$BuildMode = 'distribution',
  [Parameter(Mandatory=$true)][string]$CrystalManifest,
  [string]$CrystalApproval = '',
  [ValidatePattern('^(r[1-9][0-9]*)?$')][string]$InstallerRevision = '',
  [string]$OperationalEnvPath = '',
  [switch]$RefreshDependencies
)

$ErrorActionPreference = "Stop"
Import-Module (Join-Path $PSHOME 'Modules\Microsoft.PowerShell.Utility') -ErrorAction Stop
Import-Module (Join-Path $PSHOME 'Modules\Microsoft.PowerShell.Security') -ErrorAction Stop
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$Root = Split-Path -Parent $PSScriptRoot
$PythonExe = Join-Path $Root "BACKEND\.venv\Scripts\python.exe"
$InstallerDir = Join-Path $Root "dist\installer"
if ($BuildMode -eq 'development') {
  $InstallerDir = Join-Path $Root 'runtime\crystal-build\development\installer'
}
if ($OperationalEnvPath) { $InstallerDir = Join-Path $Root 'runtime\private-installer' }
$RuntimeDir = Join-Path $Root "runtime"
$InnoScript = Join-Path $Root "installer\AutomacaoNovelis.iss"
$VCRedistCache = Join-Path $Root "installer\cache\vc_redist.x64.exe"
$WheelhouseDir = Join-Path $Root "installer\cache\wheels"
$WheelhousePayloadDir = Join-Path $Root "runtime\installer-inputs\wheels"
$WheelRequirements = Join-Path $RuntimeDir "backend-requirements-installer.txt"
$PlaywrightCacheDir = Join-Path $Root "ms-playwright"

function Invoke-Checked {
  param(
    [Parameter(Mandatory = $true)][string]$FilePath,
    [Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments
  )
  $PreviousErrorActionPreference = $ErrorActionPreference
  try {
    $ErrorActionPreference = "Continue"
    & $FilePath @Arguments
    $ExitCode = $LASTEXITCODE
  } finally {
    $ErrorActionPreference = $PreviousErrorActionPreference
  }
  if ($ExitCode -ne 0) {
    throw "Comando falhou: $FilePath $($Arguments -join ' ')"
  }
}

function Get-AppVersion {
  $ConfigPath = Join-Path $Root "DESKTOP\automacao_novelis_desktop\config.py"
  $Content = Get-Content -LiteralPath $ConfigPath -Raw
  if ($Content -match 'APP_VERSION\s*=\s*"([^"]+)"') {
    return $Matches[1]
  }
  throw "Nao foi possivel ler APP_VERSION em $ConfigPath"
}

function Get-InnoCompiler {
  $Command = Get-Command "ISCC.exe" -ErrorAction SilentlyContinue
  if ($Command) {
    return $Command.Source
  }
  $Candidates = @(
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    "C:\Program Files\Inno Setup 6\ISCC.exe",
    "C:\Program Files\Inno Setup 7\ISCC.exe",
    (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe"),
    (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 7\ISCC.exe")
  )
  foreach ($Candidate in $Candidates) {
    if (Test-Path $Candidate) {
      return $Candidate
    }
  }
  throw "ISCC.exe nao encontrado. Instale o Inno Setup 6 e rode novamente."
}

function Ensure-VCRedistCache {
  if (!(Test-Path $VCRedistCache)) {
    New-Item -ItemType Directory -Force (Split-Path -Parent $VCRedistCache) | Out-Null
    $Url = "https://aka.ms/vs/17/release/vc_redist.x64.exe"
    Write-Host "Baixando Visual C++ Runtime para embutir no setup..."
    Invoke-WebRequest -Uri $Url -OutFile $VCRedistCache
  }
  $Signature = Get-AuthenticodeSignature -LiteralPath $VCRedistCache
  if ($Signature.Status -ne 'Valid' -or $Signature.SignerCertificate.Subject -notlike '*Microsoft Corporation*') {
    throw 'Assinatura do Visual C++ Runtime invalida.'
  }
}

function Write-BackendRequirements {
  New-Item -ItemType Directory -Force $RuntimeDir | Out-Null
  $Script = @'
import pathlib
import tomllib

root = pathlib.Path(__file__).resolve().parents[1]
data = tomllib.loads((root / "BACKEND" / "pyproject.toml").read_text(encoding="utf-8"))
deps = list(data["project"]["dependencies"])
deps.extend(data["project"]["optional-dependencies"].get("dacte", []))
deps.extend(["pip", "setuptools", "wheel"])
(root / "runtime" / "backend-requirements-installer.txt").write_text(
    "\n".join(deps) + "\n",
    encoding="utf-8",
)
'@
  $ScriptPath = Join-Path $RuntimeDir "write_backend_requirements.py"
  Set-Content -LiteralPath $ScriptPath -Value $Script -Encoding UTF8
  & $PythonExe $ScriptPath
  if ($LASTEXITCODE -ne 0) {
    throw "Nao foi possivel gerar $WheelRequirements"
  }
}

function Ensure-Wheelhouse {
  Write-BackendRequirements
  New-Item -ItemType Directory -Force $WheelhouseDir | Out-Null
  if ($RefreshDependencies -or !(Get-ChildItem -LiteralPath $WheelhouseDir -Filter '*.whl' -File)) {
    Write-Host "Baixando wheelhouse Python offline..."
    Invoke-Checked $PythonExe -m pip download --only-binary=:all: --dest $WheelhouseDir -r $WheelRequirements
  }
  New-Item -ItemType Directory -Force $WheelhousePayloadDir | Out-Null
  Get-ChildItem -LiteralPath $WheelhousePayloadDir -File -Filter '*.whl' |
    ForEach-Object { Remove-Item -LiteralPath $_.FullName -Force }
  Invoke-Checked $PythonExe -m pip download --no-index --only-binary=:all: `
    --find-links $WheelhouseDir --dest $WheelhousePayloadDir -r $WheelRequirements
}

function Install-BackendPackageForBuild {
  Write-Host "Alinhando .venv local com as dependencias empacotadas..."
  Invoke-Checked -FilePath $PythonExe -Arguments @(
    "-m",
    "pip",
    "install",
    "--no-index",
    "--find-links",
    $WheelhouseDir,
    "--upgrade",
    "pip",
    "setuptools",
    "wheel"
  )
  Invoke-Checked -FilePath $PythonExe -Arguments @(
    "-m",
    "pip",
    "install",
    "--no-index",
    "--find-links",
    $WheelhouseDir,
    "--upgrade",
    "--no-build-isolation",
    "-e",
    ((Join-Path $Root "BACKEND") + "[dacte]")
  )
}

function Get-ExpectedPlaywrightChromium {
  $env:PLAYWRIGHT_BROWSERS_PATH = $PlaywrightCacheDir
  $Script = @'
import json
from playwright.sync_api import sync_playwright

with sync_playwright() as playwright:
    print(json.dumps(playwright.chromium.executable_path, ensure_ascii=True))
'@
  try {
    $Output = $Script | & $PythonExe -
  } catch {
    return ""
  }
  if ($LASTEXITCODE -ne 0) {
    return ""
  }
  return [string](($Output | Select-Object -Last 1) | ConvertFrom-Json)
}

function Remove-StalePlaywrightChromium {
  $CacheRoot = [System.IO.Path]::GetFullPath($PlaywrightCacheDir)
  Get-ChildItem -LiteralPath $PlaywrightCacheDir -Directory -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -like "chromium*" } |
    ForEach-Object {
      $FullName = [System.IO.Path]::GetFullPath($_.FullName)
      if ($FullName.StartsWith($CacheRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        Remove-Item -LiteralPath $FullName -Recurse -Force
      }
    }
}

function Ensure-PlaywrightCache {
  New-Item -ItemType Directory -Force $PlaywrightCacheDir | Out-Null
  $ExpectedChromium = Get-ExpectedPlaywrightChromium
  if ($ExpectedChromium -and (Test-Path -LiteralPath $ExpectedChromium)) {
    return
  }
  Write-Host "Baixando Chromium do Playwright para embutir no setup..."
  $env:PLAYWRIGHT_BROWSERS_PATH = $PlaywrightCacheDir
  Remove-StalePlaywrightChromium
  Invoke-Checked $PythonExe -m playwright install chromium
}

if (-not $Version) {
  $Version = Get-AppVersion
}

if (-not (Test-Path $PythonExe)) {
  powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Root "scripts\bootstrap.ps1")
}

New-Item -ItemType Directory -Force -Path $InstallerDir, $RuntimeDir | Out-Null
$prepareArgs = @((Join-Path $Root 'scripts\prepare-installer-inputs.py'), '--mode', $BuildMode, '--crystal-manifest', $CrystalManifest)
if ($CrystalApproval) { $prepareArgs += @('--approval', $CrystalApproval) }
if ($OperationalEnvPath) { $prepareArgs += @('--operational-env', $OperationalEnvPath) }
Invoke-Checked $PythonExe @prepareArgs
if ($OperationalEnvPath) {
  $env:NOVELIS_PRIVATE_INSTALLER_DIRECTORY = $InstallerDir
  Invoke-Checked $PythonExe -c "import os,sys; from pathlib import Path; sys.path.insert(0,str(Path('scripts').resolve())); from crystal.policy import restrict_directory; restrict_directory(Path(os.environ['NOVELIS_PRIVATE_INSTALLER_DIRECTORY']))"
}
Invoke-Checked $PythonExe (Join-Path $Root 'scripts\prepare-python-runtime.py')
Invoke-Checked $PythonExe (Join-Path $Root 'scripts\prepare-webview-runtime.py')
Ensure-VCRedistCache
Ensure-Wheelhouse
Install-BackendPackageForBuild
Ensure-PlaywrightCache

Push-Location (Join-Path $Root "FRONTEND-HUB")
try {
  Invoke-Checked 'npx.cmd' 'tsc' '--noEmit'
  Invoke-Checked 'npm.cmd' 'test'
} finally {
  Pop-Location
}
Invoke-Checked -FilePath powershell.exe -Arguments @('-NoProfile', '-ExecutionPolicy', 'Bypass',
  '-File', (Join-Path $Root 'scripts\build-hub-desktop.ps1'), '-NoBundle', '-Version', $Version)

$Iscc = Get-InnoCompiler
$innoArgs = @("/DMyAppVersion=$Version")
if ($InstallerRevision) { $innoArgs += "/DInstallerRevision=$InstallerRevision" }
if ($OperationalEnvPath) { $innoArgs += '/DPrivateConfiguration' }
if ($BuildMode -eq 'development') { $innoArgs += '/DCrystalDevelopment' }
Invoke-Checked $Iscc @innoArgs $InnoScript

$SetupName = "NovelisCargoHubSetup-$Version.exe"
if ($BuildMode -eq 'development') { $SetupName = "NovelisCargoHubSetup-$Version-TESTE-NaoDistribuir.exe" }
if ($InstallerRevision) {
  $SetupName = "NovelisCargoHubSetup-$Version-$InstallerRevision.exe"
  if ($BuildMode -eq 'development') { $SetupName = "NovelisCargoHubSetup-$Version-$InstallerRevision-TESTE-NaoDistribuir.exe" }
}
if ($OperationalEnvPath) { $SetupName = $SetupName.Replace('-TESTE-NaoDistribuir', '-PRIVADO-TESTE-NaoDistribuir'); if ($BuildMode -eq 'distribution') { $SetupName = $SetupName.Replace('.exe','-PRIVADO.exe') } }
$SetupPath = Join-Path $InstallerDir $SetupName
if (-not (Test-Path $SetupPath)) {
  throw "Setup nao encontrado apos build: $SetupPath"
}

Write-Host "Instalador gerado em $SetupPath"
Invoke-Checked $PythonExe (Join-Path $Root 'scripts\setup\installer_receipt.py') --setup $SetupPath --mode $BuildMode
