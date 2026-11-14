param(
  [string]$TaskName = "AutomacaoNovelisServico"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot

function Stop-OwnedBackendProcesses {
  param([string]$InstallationRoot)
  $prefix = [IO.Path]::GetFullPath($InstallationRoot).TrimEnd('\') + '\'
  $owned = @(($prefix + 'BACKEND\.venv\'), ($prefix + 'runtime\python312\'))
  Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -in @('python.exe','pythonw.exe') -and $_.ProcessId -ne $PID } |
    ForEach-Object {
      $path = [string]$_.ExecutablePath
      if ($path -and ($path.StartsWith($owned[0], [StringComparison]::OrdinalIgnoreCase) -or
                     $path.StartsWith($owned[1], [StringComparison]::OrdinalIgnoreCase))) {
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
      }
    }
}

Set-Content -LiteralPath (Join-Path $Root "runtime\desktop-service.stop") -Value "stop" -Encoding UTF8
Remove-ItemProperty -LiteralPath 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run' -Name 'AutomacaoNovelisServico' -ErrorAction SilentlyContinue
Remove-ItemProperty -LiteralPath 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run' -Name 'Novelis Cargo Hub' -ErrorAction SilentlyContinue
Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
Stop-OwnedBackendProcesses $Root
Write-Host "Servico removido: $TaskName"
