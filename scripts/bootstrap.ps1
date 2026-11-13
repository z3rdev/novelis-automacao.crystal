param(
  [switch]$SkipFrontend,
  [switch]$SkipBackend
)

$ErrorActionPreference = "Stop"
Import-Module (Join-Path $PSHOME 'Modules\Microsoft.PowerShell.Utility') -ErrorAction Stop
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$Root = Split-Path -Parent $PSScriptRoot
$BackendDir = Join-Path $Root "BACKEND"
$FrontendDir = Join-Path $Root "FRONTEND"
$VenvDir = Join-Path $BackendDir ".venv"
$VenvPythonExe = Join-Path $BackendDir ".venv\Scripts\python.exe"
if ($env:LOCALAPPDATA) {
  $LocalPythonDir = Join-Path $env:LOCALAPPDATA "AutomacaoNovelis\python312"
} else {
  $LocalPythonDir = Join-Path $Root "runtime\python312"
}
$LocalPythonExe = Join-Path $LocalPythonDir "python.exe"
$EmbeddedPythonInstaller = Join-Path $Root "installer-cache\python-3.12.10-amd64.exe"
$WheelhouseDir = Join-Path $Root "installer-cache\wheels"
$PlaywrightPath = Join-Path $Root "ms-playwright"
$RuntimeDir = Join-Path $Root "runtime"
. (Join-Path $PSScriptRoot 'setup\bootstrap-state.ps1')
$InstalledApplication = Test-Path -LiteralPath (Join-Path $Root '.automacao-novelis-install')
if ($InstalledApplication) {
  # Never consult or repair a global Python in the installed application.
  $env:PYTHONNOUSERSITE = '1'
  Remove-Item Env:PYTHONHOME -ErrorAction SilentlyContinue
  Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
  . (Join-Path $PSScriptRoot 'setup\app-local-python.ps1')
}

function Invoke-Checked {
  param(
    [string]$FilePath,
    [string[]]$Arguments,
    [string]$WorkingDirectory
  )

  Push-Location $WorkingDirectory
  try {
    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
      throw "Comando falhou: $FilePath $($Arguments -join ' ')"
    }
  } finally {
    Pop-Location
  }
}

function Resolve-PythonCommand {
  if ($InstalledApplication) { return Resolve-AppLocalPython }
  if (Test-Path $LocalPythonExe) {
    if (Test-PythonCommand $LocalPythonExe) {
      try {
        Restore-OwnedPythonPip $LocalPythonExe
        return $LocalPythonExe
      } catch {
        Write-Host 'Pip local indisponivel. A reparacao oficial sera tentada.'
      }
    }
    Write-Host "Python local invalido. Os arquivos serao preservados para reparacao."
  }

  $installed = Resolve-InstalledPython
  if ($installed) {
    return $installed
  }

  $candidates = @("python", "py", "python3")
  foreach ($candidate in $candidates) {
    $command = Get-Command $candidate -ErrorAction SilentlyContinue
    if (-not $command) {
      continue
    }

    $source = [string]$command.Source
    if ($source -like "*\WindowsApps\python*.exe") {
      continue
    }

    if (Test-PythonBaseReady $candidate) {
      return $candidate
    }
  }

  return ""
}

function Test-PythonCommand {
  param([string]$Candidate)
  try {
    $output = & $Candidate -c "import struct,sys; print('%s.%s:%s' % (sys.version_info.major, sys.version_info.minor, struct.calcsize('P') * 8))" 2>$null
  } catch {
    return $false
  }
  if ($LASTEXITCODE -ne 0) { return $false }
  if (Test-Path -LiteralPath $WheelhouseDir) {
    # The packaged native wheels target CPython 3.12 on Windows x64.
    return ($output -eq '3.12:64')
  }
  return ($output -match '^3\.(1[1-9]|[2-9][0-9]):(32|64)$')
}

function Test-PythonBaseReady {
  param([string]$Candidate)
  if (-not (Test-PythonCommand $Candidate)) { return $false }
  try { & $Candidate -m pip --version *> $null } catch { return $false }
  return ($LASTEXITCODE -eq 0)
}

function Restore-OwnedPythonPip {
  param([string]$Candidate)
  if (-not (Test-OwnedPythonDirectory $Candidate) -or -not (Test-PythonCommand $Candidate)) {
    throw 'Reparo de pip permitido somente para Python compativel na pasta da aplicacao.'
  }
  if (Test-PythonBaseReady $Candidate) { return }
  Write-Host 'Restaurando pip offline com ensurepip do proprio Python...'
  Invoke-Checked $Candidate @('-I', '-m', 'ensurepip', '--upgrade', '--default-pip') $BackendDir | Out-Host
  if (-not (Test-PythonBaseReady $Candidate)) { throw 'Pip continuou indisponivel apos ensurepip.' }
}

function Test-VenvReady {
  if (-not (Test-Path -LiteralPath $VenvPythonExe)) {
    return $false
  }
  if (-not (Test-Path -LiteralPath (Join-Path $VenvDir "pyvenv.cfg"))) {
    return $false
  }
  if (-not (Test-PythonCommand $VenvPythonExe)) {
    return $false
  }
  try {
    & $VenvPythonExe -m pip --version *> $null
  } catch {
    return $false
  }
  return ($LASTEXITCODE -eq 0)
}

function Remove-BrokenVenv {
  if (-not (Test-Path -LiteralPath $VenvDir)) {
    return
  }
  try {
    $backendRoot = [System.IO.Path]::GetFullPath($BackendDir)
    $venvRoot = [System.IO.Path]::GetFullPath($VenvDir)
  } catch {
    return
  }
  if ($venvRoot.StartsWith($backendRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
      Where-Object {
        ($_.Name -in @("python.exe", "pythonw.exe")) -and
        ([string]$_.CommandLine).IndexOf($venvRoot, [System.StringComparison]::OrdinalIgnoreCase) -ge 0
      } |
      ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    Start-Sleep -Milliseconds 500
    Remove-Item -LiteralPath $VenvDir -Recurse -Force -ErrorAction SilentlyContinue
  }
}

function Get-PythonRegistryInstallPath {
  $keys = @(
    "HKCU:\Software\Python\PythonCore\3.12\InstallPath",
    "HKLM:\Software\Python\PythonCore\3.12\InstallPath"
  )
  foreach ($key in $keys) {
    try {
      $item = Get-Item -Path $key -ErrorAction SilentlyContinue
      if (-not $item) {
        continue
      }
      $value = [string]$item.GetValue("")
      if ($value) {
        return $value
      }
    } catch {
      continue
    }
  }
  return ""
}

function Test-OwnedPythonDirectory {
  param([string]$PathValue)
  if (-not $PathValue) { return $false }
  try {
    $candidate = [IO.Path]::GetFullPath($PathValue).TrimEnd('\')
    if ([IO.Path]::GetExtension($candidate) -eq '.exe') { $candidate = Split-Path -Parent $candidate }
    $allowed = @($LocalPythonDir)
    if ($env:LOCALAPPDATA) {
      $allowed += Join-Path $env:LOCALAPPDATA 'Programs\Automacao\runtime\python312'
      $allowed += Join-Path $env:LOCALAPPDATA 'Programs\Automacao Novelis\runtime\python312'
    }
    foreach ($directory in $allowed) {
      if ([string]::Equals($candidate, [IO.Path]::GetFullPath($directory).TrimEnd('\'), [StringComparison]::OrdinalIgnoreCase)) {
        return $true
      }
    }
  } catch { return $false }
  return $false
}

function Assert-PythonInstaller {
  param([string]$InstallerPath)
  # Published digest: python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe.sigstore
  $expected = '67b5635e80ea51072b87941312d00ec8927c4db9ba18938f7ad2d27b328b95fb'
  if ((Get-FileHash -LiteralPath $InstallerPath -Algorithm SHA256).Hash -ne $expected) {
    throw 'O instalador Python nao corresponde ao pacote oficial 3.12.10 x64 fixado.'
  }
}

function Resolve-InstalledPython {
  $paths = @()
  $registryPath = Get-PythonRegistryInstallPath
  if ($registryPath) {
    if ([System.IO.Path]::GetExtension($registryPath) -eq ".exe") {
      $paths += $registryPath
    } else {
      $paths += Join-Path $registryPath "python.exe"
    }
  }
  if ($env:LOCALAPPDATA) {
    $paths += Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe"
    $paths += Join-Path $env:LOCALAPPDATA "Programs\Python\Python311\python.exe"
    $pythonRoot = Join-Path $env:LOCALAPPDATA "Programs\Python"
    if (Test-Path $pythonRoot) {
      $paths += Get-ChildItem -LiteralPath $pythonRoot -Directory -Filter "Python3*" -ErrorAction SilentlyContinue |
        ForEach-Object { Join-Path $_.FullName "python.exe" }
    }
  }
  if ($env:ProgramFiles) {
    $paths += Join-Path $env:ProgramFiles "Python312\python.exe"
    $paths += Join-Path $env:ProgramFiles "Python311\python.exe"
  }

  foreach ($path in ($paths | Select-Object -Unique)) {
    if ((Test-Path $path) -and (Test-PythonBaseReady $path)) {
      return $path
    }
  }
  return ""
}

function Install-LocalPython {
  $RegistryInstallPath = Get-PythonRegistryInstallPath
  $TargetPythonDir = $LocalPythonDir
  $mode = 'install'
  if ($RegistryInstallPath) {
    if (-not (Test-OwnedPythonDirectory $RegistryInstallPath)) {
      throw 'Python 3.12 registrado fora da pasta da aplicacao e indisponivel. Repare essa instalacao antes de continuar.'
    }
    $TargetPythonDir = [IO.Path]::GetFullPath($RegistryInstallPath).TrimEnd('\')
    if ([IO.Path]::GetExtension($TargetPythonDir) -eq '.exe') { $TargetPythonDir = Split-Path -Parent $TargetPythonDir }
    $mode = 'repair'
  } elseif (Test-Path -LiteralPath $LocalPythonExe) {
    $mode = 'repair'
  }
  New-Item -ItemType Directory -Force $RuntimeDir | Out-Null
  $InstallerPath = $EmbeddedPythonInstaller
  if (-not (Test-Path $InstallerPath)) {
    $DownloadDir = Join-Path $Root "runtime\downloads"
    New-Item -ItemType Directory -Force $DownloadDir | Out-Null
    $InstallerPath = Join-Path $DownloadDir "python-3.12.10-amd64.exe"
    if (-not (Test-Path $InstallerPath)) {
      $Url = "https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe"
      Write-Host "Baixando Python local para a automacao..."
      Invoke-WebRequest -Uri $Url -OutFile $InstallerPath
    }
  }

  Assert-PythonInstaller $InstallerPath
  Write-Host "Preparando Python local: $mode em $TargetPythonDir"
  $InstallLog = Join-Path $RuntimeDir "python-install.log"
  $InstallerDetailLog = Join-Path $RuntimeDir "python-installer-detail.log"
  @(
    "[$(Get-Date -Format o)] Inicio da instalacao do Python local.",
    "Root=$Root",
    "InstallerPath=$InstallerPath",
    "Action=$mode",
    "LocalPythonDir=$TargetPythonDir",
    "DetailLog=$InstallerDetailLog"
  ) | Set-Content -LiteralPath $InstallLog -Encoding UTF8

  $InstallerArguments = @(
    "/quiet",
    "/norestart",
    "/log",
    "`"$InstallerDetailLog`"",
    "InstallAllUsers=0",
    "TargetDir=`"$TargetPythonDir`""
  )
  if ($mode -eq 'repair') {
    $InstallerArguments = @('/repair') + $InstallerArguments
  } else {
    $InstallerArguments += @('InstallLauncherAllUsers=0', 'PrependPath=0', 'Include_launcher=0',
      'Include_pip=1', 'Include_test=0', 'SimpleInstall=1')
  }
  $Process = Start-Process -FilePath $InstallerPath -ArgumentList $InstallerArguments -WindowStyle Hidden -Wait -PassThru
  Add-Content -LiteralPath $InstallLog -Encoding UTF8 -Value "[$(Get-Date -Format o)] Action=$mode Codigo=$($Process.ExitCode)."
  if ($Process.ExitCode -ne 0 -and $Process.ExitCode -ne 3010) {
    Add-Content -LiteralPath $InstallLog -Encoding UTF8 -Value "Falha: instalador retornou codigo $($Process.ExitCode)."
    throw "Instalador do Python falhou com codigo $($Process.ExitCode). Log: $InstallLog | Detalhe: $InstallerDetailLog"
  }
  $TargetPythonExe = Join-Path $TargetPythonDir 'python.exe'
  if (-not (Test-Path -LiteralPath $TargetPythonExe) -or -not (Test-PythonCommand $TargetPythonExe)) {
    throw "Python e pip nao ficaram funcionais apos $mode. Log: $InstallLog | Detalhe: $InstallerDetailLog"
  }
  Restore-OwnedPythonPip $TargetPythonExe
  Add-Content -LiteralPath $InstallLog -Encoding UTF8 -Value "Python e pip funcionais: $TargetPythonExe"
  return $TargetPythonExe
}

function Test-PlaywrightChromium {
  if (-not (Test-Path $PlaywrightPath)) {
    return $false
  }
  $Script = @'
from pathlib import Path
from playwright.sync_api import sync_playwright

with sync_playwright() as playwright:
    print('present' if Path(playwright.chromium.executable_path).is_file() else 'missing')
'@
  try {
    $Output = $Script | & $VenvPythonExe -
  } catch {
    return $false
  }
  if ($LASTEXITCODE -ne 0) {
    return $false
  }
  return ([string]($Output | Select-Object -Last 1) -eq 'present')
}

function Get-RequiredPlaywrightSpec {
  $Pyproject = Join-Path $BackendDir "pyproject.toml"
  if (Test-Path $Pyproject) {
    $Content = Get-Content -LiteralPath $Pyproject -Raw
    if ($Content -match '"(playwright[^"]*)"') {
      return $Matches[1]
    }
  }
  return "playwright==1.61.0"
}

function Test-PlaywrightDriverPackage {
  $DriverDir = Join-Path $BackendDir ".venv\Lib\site-packages\playwright\driver"
  $Cli = Join-Path $DriverDir "package\cli.js"
  $Node = Join-Path $DriverDir "node.exe"
  return ((Test-Path -LiteralPath $Cli) -and (Test-Path -LiteralPath $Node))
}

function Repair-PlaywrightPackage {
  $Spec = Get-RequiredPlaywrightSpec
  Write-Host "Playwright incompleto. Reinstalando $Spec..."
  if (Test-Path $WheelhouseDir) {
    Invoke-Checked $VenvPythonExe @(
      "-m",
      "pip",
      "install",
      "--no-index",
      "--find-links",
      $WheelhouseDir,
      "--force-reinstall",
      "--no-deps",
      $Spec
    ) $BackendDir
  } else {
    Invoke-Checked $VenvPythonExe @("-m", "pip", "install", "--force-reinstall", "--no-deps", $Spec) $BackendDir
  }
  if (-not (Test-PlaywrightDriverPackage)) {
    throw "Playwright continuou incompleto apos reinstalacao. Driver cli.js/node.exe nao encontrados."
  }
}

function Install-BackendPackage {
  if (Test-Path $WheelhouseDir) {
    Write-Host "Instalando dependencias Python pela wheelhouse offline..."
    Invoke-Checked $VenvPythonExe @(
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
    ) $BackendDir
    Invoke-Checked $VenvPythonExe @(
      "-m",
      "pip",
      "install",
      "--no-index",
      "--find-links",
      $WheelhouseDir,
      "--upgrade",
      "--no-build-isolation",
      "-e",
      ".[dacte]"
    ) $BackendDir
    return
  }

  Invoke-Checked $VenvPythonExe @("-m", "pip", "install", "--upgrade", "pip") $BackendDir
  Invoke-Checked $VenvPythonExe @("-m", "pip", "install", "--upgrade", "-e", ".[dacte]") $BackendDir
}

$BootstrapLock = Enter-BootstrapLock
try {
Start-BootstrapLog
try {
if (-not $SkipBackend) {
  Set-BootstrapStage 'python_resolution'
  if ($InstalledApplication) {
    Assert-InstalledOfflineInputs
    $AppPython = Resolve-AppLocalPython
  }
  if (-not (Test-VenvReady)) {
    if (Test-Path -LiteralPath $VenvDir) {
      Write-Host "Venv local invalida. Recriando $VenvDir"
      Remove-BrokenVenv
    }
    $SystemPython = if ($InstalledApplication) { $AppPython } else { Resolve-PythonCommand }
    if (-not $SystemPython) {
      Set-BootstrapStage 'python_installation'
      $SystemPython = Install-LocalPython
    }
    Set-BootstrapStage 'venv_creation'
    Invoke-Checked $SystemPython @("-m", "venv", ".venv") $BackendDir
  }
  Set-BootstrapStage 'venv_validation'
  if (-not (Test-VenvReady)) {
    throw "Venv local continuou invalida: $VenvDir"
  }

  Set-BootstrapStage 'backend_dependencies'
  Install-BackendPackage
  Set-BootstrapStage 'backend_imports'
  Invoke-Checked $VenvPythonExe @('-c', 'import fastapi, uvicorn, playwright.sync_api, pyodbc, qrcode, pypdf, pypdfium2, zxingcpp') $BackendDir
  Set-BootstrapStage 'playwright_package'
  if (-not (Test-PlaywrightDriverPackage)) {
    Repair-PlaywrightPackage
  }
  New-Item -ItemType Directory -Force $PlaywrightPath | Out-Null
  $env:PLAYWRIGHT_BROWSERS_PATH = $PlaywrightPath
  Set-BootstrapStage 'playwright_browser'
  if (-not (Test-PlaywrightChromium)) {
    if ($InstalledApplication) { throw 'Chromium offline ausente ou incompativel no pacote.' }
    Invoke-Checked $VenvPythonExe @("-m", "playwright", "install", "chromium") $BackendDir
  } else {
    Write-Host "Playwright Chromium ja esta empacotado em $PlaywrightPath"
  }
  if ($InstalledApplication) {
    Set-BootstrapStage 'backend_health'
    Invoke-Checked $VenvPythonExe @('-I', (Join-Path $PSScriptRoot 'setup\verify_backend.py'), '--root', $Root) $BackendDir
  }
}

if (-not $SkipFrontend) {
  Set-BootstrapStage 'frontend_dependencies'
  Invoke-Checked "npm" @("install") $FrontendDir
}

Write-Host "Bootstrap finalizado."
Set-BootstrapStage 'complete'
Write-BootstrapResult 'succeeded' 0
} catch {
  Write-BootstrapResult 'failed' 1
  Write-Host "Bootstrap falhou na etapa $script:BootstrapStage. Log: $script:BootstrapLog"
  Write-Host ([string]$_)
  exit 1
} finally {
  Stop-Transcript | Out-Null
}
} finally { $BootstrapLock.Dispose() }
exit 0
