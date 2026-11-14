param(
  [string]$TaskName = "AutomacaoNovelisServico",
  [switch]$SkipExecutableBuild,
  [switch]$SkipShortcut
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$PythonwExe = Join-Path $Root "BACKEND\.venv\Scripts\pythonw.exe"
$PythonExe = Join-Path $Root "BACKEND\.venv\Scripts\python.exe"
$ServiceScript = Join-Path $Root "DESKTOP\run_service.py"
$DesktopExe = Join-Path $Root "dist\desktop\AutomacaoNovelis\AutomacaoNovelis.exe"
$LegacyDesktopExe = Join-Path $Root "dist\desktop\AutomacaoNovelis.exe"
$ShortcutPath = Join-Path ([Environment]::GetFolderPath("Desktop")) "Automacao Novelis.lnk"
$IconPath = Join-Path $Root "FRONTEND\src\assets\icon.desktop.ico"
$CurrentUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name

if ((Test-Path -LiteralPath (Join-Path $Root 'novelis-cargo-hub.exe')) -and (Test-Path -LiteralPath $PythonwExe)) {
  # Migrate the legacy Python worker to the native tray application when startup was enabled.
  $RunKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'
  $OldStartup = Get-ItemPropertyValue -LiteralPath $RunKey -Name 'AutomacaoNovelisServico' -ErrorAction SilentlyContinue
  $NativeStartup = Get-ItemPropertyValue -LiteralPath $RunKey -Name 'Novelis Cargo Hub' -ErrorAction SilentlyContinue
  $OldStartupEnabled = [bool]$OldStartup
  $Approval = Get-ItemPropertyValue -LiteralPath 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run' -Name 'AutomacaoNovelisServico' -ErrorAction SilentlyContinue
  if ($Approval -and $Approval.Length -ge 8) {
    # Respect a legacy startup disabled through Task Manager.
    $OldStartupEnabled = $OldStartupEnabled -and -not ($Approval[($Approval.Length - 8)..($Approval.Length - 1)] | Where-Object { $_ -ne 0 })
  }
  if ($OldStartupEnabled -or $NativeStartup) {
    New-Item -Path $RunKey -Force | Out-Null
    $Command = '"' + (Join-Path $Root 'novelis-cargo-hub.exe') + '" --background'
    New-ItemProperty -Path $RunKey -Name 'Novelis Cargo Hub' -Value $Command -PropertyType String -Force | Out-Null
  }
  Remove-ItemProperty -LiteralPath $RunKey -Name 'AutomacaoNovelisServico' -ErrorAction SilentlyContinue
  Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
  Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
  Set-Content -LiteralPath (Join-Path $Root 'runtime\desktop-service.stop') -Value 'stop' -Encoding UTF8
  Write-Host 'Cargo Hub usa a bandeja e a opcao Iniciar com o Windows nas configuracoes do aplicativo.'
  exit 0
}

if (-not (Test-Path $PythonExe)) {
  powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Root "scripts\bootstrap.ps1") -SkipFrontend
}

if (Test-Path $PythonwExe) {
  $Runner = $PythonwExe
} elseif (Test-Path $PythonExe) {
  $Runner = $PythonExe
} else {
  Write-Host "Backend nao tem .venv. Rode scripts\bootstrap.ps1 primeiro." -ForegroundColor Yellow
  exit 1
}

if (-not (Test-Path $DesktopExe) -and (Test-Path $LegacyDesktopExe)) {
  $DesktopExe = $LegacyDesktopExe
}

if (-not $SkipExecutableBuild -and -not (Test-Path $DesktopExe)) {
  powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Root "scripts\build-desktop.ps1")
}

if (-not $SkipShortcut -and (Test-Path $DesktopExe)) {
  $Shell = New-Object -ComObject WScript.Shell
  $Shortcut = $Shell.CreateShortcut($ShortcutPath)
  $Shortcut.TargetPath = $DesktopExe
  $Shortcut.Arguments = ""
  $Shortcut.WorkingDirectory = $Root
  if (Test-Path $IconPath) {
    $Shortcut.IconLocation = "$IconPath,0"
  }
  $Shortcut.Description = "Automação Novelis"
  $Shortcut.Save()
  Write-Host "Atalho criado em $ShortcutPath"
}

New-Item -ItemType Directory -Force (Join-Path $Root "runtime") | Out-Null
Remove-Item -LiteralPath (Join-Path $Root "runtime\desktop-service.stop") -Force -ErrorAction SilentlyContinue

$Action = New-ScheduledTaskAction -Execute $Runner -Argument "`"$ServiceScript`"" -WorkingDirectory $Root
$LogonTrigger = New-ScheduledTaskTrigger -AtLogOn -User $CurrentUser
$StartupTrigger = New-ScheduledTaskTrigger -AtStartup
$Settings = New-ScheduledTaskSettingsSet `
  -AllowStartIfOnBatteries `
  -DontStopIfGoingOnBatteries `
  -MultipleInstances IgnoreNew `
  -RestartCount 3 `
  -RestartInterval (New-TimeSpan -Minutes 1) `
  -StartWhenAvailable

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger @($StartupTrigger, $LogonTrigger) -Settings $Settings -Force | Out-Null
Start-ScheduledTask -TaskName $TaskName
Write-Host "Servico persistente instalado/iniciado: $TaskName"
Write-Host "Ao iniciar, o servico sobe backend e frontend locais."
