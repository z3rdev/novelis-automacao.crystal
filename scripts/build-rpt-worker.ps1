param([switch]$Release, [ValidateRange(1,4)][int]$Jobs=1)
$ErrorActionPreference='Stop'
$Root=Split-Path -Parent $PSScriptRoot
$VsWhere=Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
$VisualCpp=& $VsWhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
if (!$VisualCpp) { throw 'MSVC x64 e Windows SDK sao necessarios para compilar o worker.' }
$DevCmd=Join-Path $VisualCpp 'Common7\Tools\VsDevCmd.bat'
$CompilerEnvironment=& cmd.exe /d /c "call `"$DevCmd`" -no_logo -arch=x64 -host_arch=x64 >nul && set"
if ($LASTEXITCODE -ne 0) { throw 'Falha ao carregar ambiente MSVC.' }
foreach ($line in $CompilerEnvironment) {
    if ($line -match '^([^=]+)=(.*)$') { [Environment]::SetEnvironmentVariable($Matches[1],$Matches[2],'Process') }
}
$env:CARGO_BUILD_JOBS=[string]$Jobs
Push-Location -LiteralPath (Join-Path $Root 'rpt-worker')
try {
    $arguments=@('build')
    if (Test-Path -LiteralPath 'Cargo.lock') { $arguments+='--locked' }
    if ($Release) { $arguments+='--release' }
    & cargo @arguments
    $exitCode=$LASTEXITCODE
} finally { Pop-Location }
if ($exitCode -ne 0) { throw 'Compilacao do worker rpt-rs falhou.' }
