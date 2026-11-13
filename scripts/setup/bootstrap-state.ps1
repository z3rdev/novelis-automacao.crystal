# Bootstrap logs contain dependency preparation only; never read application .env files.
function Enter-BootstrapLock {
  param([int]$WaitSeconds = 600)
  New-Item -ItemType Directory -Path $RuntimeDir -Force | Out-Null
  $deadline = [DateTime]::UtcNow.AddSeconds($WaitSeconds)
  $announced = $false
  while ($true) {
    try {
      return [IO.File]::Open((Join-Path $RuntimeDir 'bootstrap.lock'),
        [IO.FileMode]::OpenOrCreate, [IO.FileAccess]::ReadWrite, [IO.FileShare]::None)
    } catch [IO.IOException] {
      if ([DateTime]::UtcNow -ge $deadline) { throw 'Outra preparacao do backend continua em execucao.' }
      if (!$announced) { Write-Host 'Aguardando outra preparacao do backend terminar...'; $announced = $true }
      Start-Sleep -Milliseconds 250
    }
  }
}

function Set-BootstrapStage {
  param([string]$Stage)
  $script:BootstrapStage = $Stage
  Write-Host "[bootstrap] $Stage"
}

function Write-BootstrapResult {
  param([string]$Status, [int]$ExitCode)
  $result = [ordered]@{
    schema_version = 1
    status = $Status
    stage = $script:BootstrapStage
    exit_code = $ExitCode
    checked_at = [DateTime]::UtcNow.ToString('o')
    process_bits = [IntPtr]::Size * 8
    process_id = $PID
    identity = [Security.Principal.WindowsIdentity]::GetCurrent().Name
    venv_python_exists = Test-Path -LiteralPath $VenvPythonExe
    offline_wheels = Test-Path -LiteralPath $WheelhouseDir
    log = $script:BootstrapLog
  }
  $result | ConvertTo-Json | Set-Content -LiteralPath $script:BootstrapResult -Encoding UTF8
  Set-Content -LiteralPath ($script:BootstrapResult + '.exitcode') -Value $ExitCode -Encoding ASCII
}

function Start-BootstrapLog {
  New-Item -ItemType Directory -Path $RuntimeDir -Force | Out-Null
  $script:BootstrapLog = Join-Path $RuntimeDir 'bootstrap.log'
  $script:BootstrapResult = Join-Path $RuntimeDir 'bootstrap-result.json'
  $script:BootstrapStage = 'initialization'
  Remove-Item -LiteralPath ($script:BootstrapResult + '.exitcode') -Force -ErrorAction SilentlyContinue
  Start-Transcript -LiteralPath $script:BootstrapLog -Append -Force | Out-Null
}
