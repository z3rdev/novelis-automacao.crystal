param(
  [Parameter(Mandatory = $true)][string]$InstallRoot,
  [switch]$DryRun
)
$ErrorActionPreference = 'Stop'

# Never select processes just because they use port 8000 or are named python.exe.
$resolvedRoot = [IO.Path]::GetFullPath($InstallRoot).TrimEnd('\')
if ($resolvedRoot.StartsWith('\\') -or $resolvedRoot.Length -lt 5 -or
    -not (Test-Path -LiteralPath (Join-Path $resolvedRoot '.automacao-novelis-install') -PathType Leaf)) {
  throw 'Pasta de instalacao Cargo Hub nao reconhecida. Encerramento cancelado.'
}
$rootPrefix = $resolvedRoot + '\'
if (-not $DryRun) {
  $task = Get-ScheduledTask -TaskName 'AutomacaoNovelisServico' -ErrorAction SilentlyContinue
  if ($task -and @($task.Actions | Where-Object {
      ($_.Execute -and $_.Execute.StartsWith($rootPrefix, [StringComparison]::OrdinalIgnoreCase)) -or
      ($_.Arguments -and $_.Arguments.IndexOf($rootPrefix, [StringComparison]::OrdinalIgnoreCase) -ge 0)
    }).Count) {
    Stop-ScheduledTask -InputObject $task -ErrorAction Stop
  }
}
$allProcesses = @(Get-CimInstance Win32_Process)
$excluded = [Collections.Generic.HashSet[int]]::new()
$cursorPid = [int]$PID
$visited = [Collections.Generic.HashSet[int]]::new()
while ($cursorPid -gt 0 -and $visited.Add($cursorPid)) {
  $parent = $allProcesses | Where-Object { $_.ProcessId -eq $cursorPid } | Select-Object -First 1
  if (-not $parent) { break }
  if ($cursorPid -eq $PID -or $parent.Name -match '(?i)setup|unins') { [void]$excluded.Add($cursorPid) }
  $cursorPid = [int]$parent.ParentProcessId
}
$owned = [Collections.Generic.HashSet[int]]::new()
$allowedNames = @('novelis-cargo-hub.exe','AutomacaoNovelis.exe','python.exe','pythonw.exe',
  'powershell.exe','pwsh.exe','node.exe','msedge.exe','chrome.exe','msedgewebview2.exe')
foreach ($process in $allProcesses) {
  if ($excluded.Contains([int]$process.ProcessId) -or $process.Name -notin $allowedNames) { continue }
  $executableOwned = $process.ExecutablePath -and $process.ExecutablePath.StartsWith($rootPrefix, [StringComparison]::OrdinalIgnoreCase)
  $commandOwned = $process.CommandLine -and $process.CommandLine.IndexOf($rootPrefix, [StringComparison]::OrdinalIgnoreCase) -ge 0
  if ($executableOwned -or $commandOwned) { [void]$owned.Add([int]$process.ProcessId) }
}
# Only descendants already present in this snapshot are candidates; PID and creation
# time are checked again immediately before terminating each process.
do {
  $added = $false
  foreach ($process in $allProcesses) {
    if ($owned.Contains([int]$process.ParentProcessId) -and -not $excluded.Contains([int]$process.ProcessId)) {
      if ($owned.Add([int]$process.ProcessId)) { $added = $true }
    }
  }
} while ($added)
$candidates = @($allProcesses | Where-Object { $owned.Contains([int]$_.ProcessId) })
if (-not $DryRun) {
  foreach ($process in $candidates) {
    $live = Get-Process -Id $process.ProcessId -ErrorAction SilentlyContinue
    if ($live -and $live.MainWindowHandle -ne 0) { [void]$live.CloseMainWindow() }
  }
  if ($candidates.Count) { Start-Sleep -Seconds 3 }
  foreach ($process in $candidates) {
    $live = Get-CimInstance Win32_Process -Filter "ProcessId=$($process.ProcessId)"
    if ($live -and $live.CreationDate -eq $process.CreationDate) {
      Stop-Process -Id $process.ProcessId -Force -ErrorAction Stop
    }
  }
  $remaining = @()
  foreach ($process in $candidates) {
    $live = Get-CimInstance Win32_Process -Filter "ProcessId=$($process.ProcessId)"
    if ($live -and $live.CreationDate -eq $process.CreationDate) { $remaining += $live }
  }
  if ($remaining.Count) { throw 'Ainda existem processos do Cargo Hub ativos. Atualizacao interrompida.' }
}
[pscustomobject]@{ schema_version=1; dry_run=[bool]$DryRun; matched=$candidates.Count; unrelated_processes_stopped=$false } | ConvertTo-Json -Compress
