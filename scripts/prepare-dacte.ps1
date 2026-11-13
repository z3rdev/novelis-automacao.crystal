param(
    [switch]$Repair,
    [switch]$Assist,
    [switch]$Silent,
    [switch]$NoElevation,
    [switch]$NoDatabase,
    [string]$InputFile = '',
    [int]$Filial = 0,
    [string]$Serie = '',
    [int]$Documento = 0,
    [string]$XmlReference = ''
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot 'BACKEND\.venv\Scripts\python.exe'
$reportDir = Join-Path $projectRoot 'runtime\installation'
New-Item -ItemType Directory -Path $reportDir -Force | Out-Null
if (!(Test-Path -LiteralPath $python)) {
    @{status='pending';message='Python do backend ausente. Execute bootstrap.ps1.'} |
        ConvertTo-Json | Set-Content -LiteralPath (Join-Path $reportDir 'dacte-diagnostic.json') -Encoding UTF8
    '<!doctype html><meta charset="utf-8"><h1>Diagnostico DACTE pendente</h1><p>Python do backend ausente. Execute scripts/bootstrap.ps1 e repita a preparacao.</p>' |
        Set-Content -LiteralPath (Join-Path $reportDir 'dacte-diagnostic.html') -Encoding UTF8
    exit 2
}
$arguments = @('-m', 'app.tools.dacte_setup')
if ($Repair) { $arguments += '--repair' }
if ($Assist) { $arguments += '--assist' }
if ($Silent) { $arguments += '--silent' }
if ($NoDatabase) { $arguments += '--no-database' }
if ($InputFile) { $arguments += @('--inputs', $InputFile) }
if ($Filial -and $Serie -and $Documento) {
    $arguments += @('--filial', [string]$Filial, '--serie', $Serie, '--documento', [string]$Documento)
}
if ($XmlReference) { $arguments += @('--xml-reference', $XmlReference) }
Push-Location (Join-Path $projectRoot 'BACKEND')
try {
    & $python @arguments 2>&1 | Tee-Object -FilePath (Join-Path $reportDir 'dacte-setup.log')
    $exitCode = $LASTEXITCODE
} finally { Pop-Location }
if ($exitCode -eq 3 -and $Repair -and $Assist -and !$Silent -and !$NoElevation) {
    $elevatedArgs = @('-NoProfile','-ExecutionPolicy','Bypass','-File',('"' + $PSCommandPath + '"'),'-Repair','-Assist','-NoElevation')
    if ($InputFile) { $elevatedArgs += @('-InputFile', ('"' + $InputFile + '"')) }
    if ($NoDatabase) { $elevatedArgs += '-NoDatabase' }
    if ($Filial -and $Serie -and $Documento) {
        $elevatedArgs += @('-Filial', [string]$Filial, '-Serie', ('"' + $Serie + '"'), '-Documento', [string]$Documento)
    }
    if ($XmlReference) { $elevatedArgs += @('-XmlReference', ('"' + $XmlReference + '"')) }
    $process = Start-Process -FilePath 'powershell.exe' -ArgumentList $elevatedArgs -Verb RunAs -WindowStyle Hidden -Wait -PassThru
    exit $process.ExitCode
}
exit $exitCode
