param(
  [switch]$InstallService,
  [switch]$SkipBuildDesktop,
  [switch]$SkipShortcut
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$ShortcutPath = Join-Path ([Environment]::GetFolderPath("Desktop")) "Automacao Novelis.lnk"
$IconPath = Join-Path $Root "FRONTEND\src\assets\icon.desktop.ico"

powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Root "scripts\bootstrap.ps1")

Push-Location (Join-Path $Root "FRONTEND")
try {
  npm run build
} finally {
  Pop-Location
}

if (-not $SkipBuildDesktop) {
  powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Root "scripts\build-desktop.ps1")
}

if (-not $SkipShortcut) {
  $Target = Join-Path $Root "dist\desktop\AutomacaoNovelis\AutomacaoNovelis.exe"
  if (-not (Test-Path $Target)) {
    $Target = Join-Path $Root "dist\desktop\AutomacaoNovelis.exe"
  }
  if (-not (Test-Path $Target)) {
    $Target = "powershell.exe"
    $Arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$Root\scripts\desktop-app.ps1`""
  } else {
    $Arguments = ""
  }
  $Shell = New-Object -ComObject WScript.Shell
  $Shortcut = $Shell.CreateShortcut($ShortcutPath)
  $Shortcut.TargetPath = $Target
  $Shortcut.Arguments = $Arguments
  $Shortcut.WorkingDirectory = $Root
  if (Test-Path $IconPath) {
    $Shortcut.IconLocation = "$IconPath,0"
  }
  $Shortcut.Description = "Automação Novelis"
  $Shortcut.Save()
  Write-Host "Atalho criado em $ShortcutPath"
}

if ($InstallService) {
  $ServiceArgs = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", (Join-Path $Root "scripts\install-desktop-service.ps1"))
  if (-not $SkipBuildDesktop) {
    $ServiceArgs += "-SkipExecutableBuild"
  }
  if (-not $SkipShortcut) {
    $ServiceArgs += "-SkipShortcut"
  }
  powershell @ServiceArgs
}

Write-Host "Instalacao finalizada."
