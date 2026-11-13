param(
  [string]$InstallationRoot = '',
  [switch]$CollectOnly
)
$ErrorActionPreference = 'Stop'
if (!$InstallationRoot) {
  $registered = Get-ItemProperty -LiteralPath 'HKCU:\Software\AutomacaoNovelis' -ErrorAction SilentlyContinue
  if ($registered) { $InstallationRoot = [string]$registered.InstallRoot }
}
if (!$InstallationRoot) {
  $InstallationRoot = Join-Path $env:LOCALAPPDATA 'Programs\Automacao Novelis'
}
$InstallationRoot = [IO.Path]::GetFullPath($InstallationRoot)
if (!(Test-Path -LiteralPath (Join-Path $InstallationRoot '.automacao-novelis-install')) -or
    !(Test-Path -LiteralPath (Join-Path $InstallationRoot 'BACKEND\pyproject.toml'))) {
  throw 'Pasta instalada nao identificada. Informe -InstallationRoot com a pasta do aplicativo.'
}
$runtime = Join-Path $InstallationRoot 'runtime'
$snapshot = Join-Path $runtime ('backend-recovery\' + [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ'))
New-Item -ItemType Directory -Path $snapshot -Force | Out-Null
$logNames = @('stack-start.log', 'python-install.log', 'python-installer-detail.log',
  'python-uninstall-detail.log', 'bootstrap.log', 'bootstrap-result.json')
function Save-RecoveryLogs {
  param([string]$Prefix)
  $names = @($logNames)
  foreach ($pattern in @('python-installer-detail_*.log', 'python-uninstall-detail_*.log')) {
    $names += Get-ChildItem -LiteralPath $runtime -Filter $pattern -File -ErrorAction SilentlyContinue |
      Select-Object -ExpandProperty Name
  }
  foreach ($name in ($names | Select-Object -Unique)) {
    $source = Join-Path $runtime $name
    if (Test-Path -LiteralPath $source) {
      Copy-Item -LiteralPath $source -Destination (Join-Path $snapshot ($Prefix + $name))
    }
  }
}
Save-RecoveryLogs 'before-'
$pythonRegistrations = @()
foreach ($hive in @([Microsoft.Win32.RegistryHive]::CurrentUser, [Microsoft.Win32.RegistryHive]::LocalMachine)) {
  foreach ($view in @([Microsoft.Win32.RegistryView]::Registry64, [Microsoft.Win32.RegistryView]::Registry32)) {
    $base = $null
    $key = $null
    try {
      $base = [Microsoft.Win32.RegistryKey]::OpenBaseKey($hive, $view)
      $key = $base.OpenSubKey('Software\Python\PythonCore\3.12\InstallPath')
      if ($key) {
        $pythonRegistrations += [ordered]@{hive=[string]$hive; view=[string]$view; path=[string]$key.GetValue('')}
      }
    } finally {
      if ($key) { $key.Dispose() }
      if ($base) { $base.Dispose() }
    }
  }
}
$state = [ordered]@{
  schema_version = 1
  checked_at = [DateTime]::UtcNow.ToString('o')
  computer = $env:COMPUTERNAME
  identity = [Security.Principal.WindowsIdentity]::GetCurrent().Name
  installation_root = $InstallationRoot
  process_bits = [IntPtr]::Size * 8
  python_registrations = $pythonRegistrations
  embedded_python_installer_exists = Test-Path -LiteralPath (Join-Path $InstallationRoot 'installer-cache\python-3.12.10-amd64.exe')
  local_python_exists = Test-Path -LiteralPath (Join-Path $env:LOCALAPPDATA 'AutomacaoNovelis\python312\python.exe')
  venv_python_exists = Test-Path -LiteralPath (Join-Path $InstallationRoot 'BACKEND\.venv\Scripts\python.exe')
  mode = $(if ($CollectOnly) { 'collect_only' } else { 'repair' })
  status = 'collected'
  production_ready = $false
}
$exitCode = 0
try {
  if (!$CollectOnly) {
    # This kit contains only project scripts; never copy runtime DLLs, keys or .env.
    $updates = @('bootstrap.ps1', 'run-dev.ps1', 'setup\bootstrap-state.ps1')
    foreach ($relative in $updates) {
      if (!(Test-Path -LiteralPath (Join-Path $PSScriptRoot $relative))) {
        throw 'Kit incompleto. Extraia todos os arquivos antes de executar.'
      }
    }
    foreach ($relative in $updates) {
      $source = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot $relative))
      $destination = [IO.Path]::GetFullPath((Join-Path $InstallationRoot ('scripts\' + $relative)))
      if ($source -eq $destination) { continue }
      if (Test-Path -LiteralPath $destination) {
        $backup = Join-Path $snapshot ('scripts-before\' + $relative)
        New-Item -ItemType Directory -Path (Split-Path -Parent $backup) -Force | Out-Null
        Copy-Item -LiteralPath $destination -Destination $backup
      }
      New-Item -ItemType Directory -Path (Split-Path -Parent $destination) -Force | Out-Null
      Copy-Item -LiteralPath $source -Destination $destination -Force
    }
    $shell = Join-Path $env:WINDIR 'System32\WindowsPowerShell\v1.0\powershell.exe'
    if ([Environment]::Is64BitOperatingSystem -and ![Environment]::Is64BitProcess) {
      $shell = Join-Path $env:WINDIR 'Sysnative\WindowsPowerShell\v1.0\powershell.exe'
    }
    & $shell -NoProfile -NonInteractive -ExecutionPolicy Bypass `
      -File (Join-Path $InstallationRoot 'scripts\bootstrap.ps1') -SkipFrontend
    $exitCode = $LASTEXITCODE
    $state.bootstrap_exit_code = $exitCode
    $venv = Join-Path $InstallationRoot 'BACKEND\.venv\Scripts\python.exe'
    $state.venv_python_exists = Test-Path -LiteralPath $venv
    if ($exitCode -ne 0 -or !$state.venv_python_exists) {
      $state.status = 'repair_failed'
      $exitCode = 1
    } else {
      $state.status = 'backend_prepared'
    }
  }
} catch {
  $state.status = 'repair_failed'
  $exitCode = 1
  Write-Host ([string]$_)
} finally {
  Save-RecoveryLogs 'after-'
  $state | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $snapshot 'recovery.json') -Encoding UTF8
  $archive = $snapshot + '.zip'
  Compress-Archive -LiteralPath $snapshot -DestinationPath $archive -Force
  Write-Host "RECOVERY_STATUS=$($state.status)"
  Write-Host "RECOVERY_REPORT=$archive"
}
exit $exitCode
