param([string]$OutputPath = '')
$root = Split-Path -Parent $PSScriptRoot
$probe = Join-Path $root 'installer\crystal\inspect-runtime.ps1'
$ps32 = Join-Path $env:SystemRoot 'SysWOW64\WindowsPowerShell\v1.0\powershell.exe'
& $ps32 -NoProfile -NonInteractive -STA -ExecutionPolicy Bypass -File $probe -OutputPath $OutputPath
exit $LASTEXITCODE
