$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$directory = Join-Path $root 'runtime\tools\wix-4.0.6'
$package = Join-Path $directory 'wix.4.0.6.nupkg'
$expected = 'A94DD42AE1FB56B32DA180E2173CEDA4F0D10B4C8871C5EE59ECB502131A1EB6'
New-Item -ItemType Directory -Path $directory -Force | Out-Null
if (!(Test-Path -LiteralPath $package)) {
    Invoke-WebRequest -Uri 'https://api.nuget.org/v3-flatcontainer/wix/4.0.6/wix.4.0.6.nupkg' -OutFile $package
}
if ((Get-FileHash -LiteralPath $package -Algorithm SHA256).Hash -ne $expected) {
    throw 'WiX diferente da versao inventariada.'
}
if (!(Test-Path (Join-Path $directory 'tools\net6.0\any\wix.dll'))) {
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [IO.Compression.ZipFile]::ExtractToDirectory($package, $directory)
}
Write-Output 'WiX 4.0.6 pronto para build local; requer .NET Runtime 6.'
