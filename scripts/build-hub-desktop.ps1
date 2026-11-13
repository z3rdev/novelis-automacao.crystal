param([switch]$Debug, [switch]$NoBundle, [string]$Version = '', [ValidateRange(1,4)][int]$Jobs = 1)
$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$HubRoot = Join-Path $ProjectRoot 'FRONTEND-HUB'
$env:CARGO_BUILD_JOBS = [string]$Jobs
$VsWhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
$VisualCpp = if (Test-Path -LiteralPath $VsWhere) {
    & $VsWhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
}
if (-not $VisualCpp) {
    throw 'Instale a carga Desenvolvimento para desktop com C++ no Visual Studio Build Tools, incluindo MSVC x64/x86 e Windows SDK. A instalacao atual nao contem o linker link.exe.'
}
if (-not (Get-Command cargo -ErrorAction SilentlyContinue)) {
    throw 'Rust/Cargo nao encontrado. Instale o toolchain MSVC do Rust para Windows.'
}
# Import the MSVC/Windows SDK environment without changing global PATH settings.
$DevCmd = Join-Path $VisualCpp 'Common7\Tools\VsDevCmd.bat'
$CompilerEnvironment = & cmd.exe /d /c "call `"$DevCmd`" -no_logo -arch=x64 -host_arch=x64 >nul && set"
if ($LASTEXITCODE -ne 0) { throw 'Falha ao carregar ambiente MSVC x64.' }
foreach ($line in $CompilerEnvironment) {
    if ($line -match '^([^=]+)=(.*)$') { [Environment]::SetEnvironmentVariable($Matches[1], $Matches[2], 'Process') }
}
Push-Location -LiteralPath $HubRoot
try {
    if (-not (Test-Path -LiteralPath 'node_modules')) {
        & npm.cmd ci
        if ($LASTEXITCODE -ne 0) { throw 'Falha ao instalar dependencias do frontend.' }
    }
    & npx.cmd tsc --noEmit
    if ($LASTEXITCODE -ne 0) { throw 'Verificacao TypeScript falhou.' }
    $BuildArguments = @('tauri', 'build')
    if (!$Version) {
        $VersionSource = Get-Content -LiteralPath (Join-Path $ProjectRoot 'DESKTOP\automacao_novelis_desktop\config.py') -Raw
        if ($VersionSource -notmatch 'APP_VERSION\s*=\s*"([^"]+)"') { throw 'Versao da aplicacao ausente.' }
        $Version = $Matches[1]
    }
    $ConfigOverride = Join-Path $ProjectRoot 'runtime\hub-build-config.json'
    New-Item -ItemType Directory -Force (Split-Path -Parent $ConfigOverride) | Out-Null
    @{version=$Version} | ConvertTo-Json | Set-Content -LiteralPath $ConfigOverride -Encoding UTF8
    $BuildArguments += @('--config', $ConfigOverride)
    if ($Debug) { $BuildArguments += '--debug' }
    if ($NoBundle) { $BuildArguments += '--no-bundle' }
    & npx.cmd @BuildArguments
    if ($LASTEXITCODE -ne 0) { throw 'Compilacao Tauri falhou.' }
} finally {
    Pop-Location
}
