param([string]$DataDirectory = '', [int]$Port = 8000)
$ErrorActionPreference = 'Stop'
$DatabasePath = if ($DataDirectory) { Join-Path $DataDirectory 'novelischamado.sqlite' } else { '\\192.168.254.250\rede\Publico\novelis-automacao\novelischamado.sqlite' }
Write-Host 'O backend agora e local em cada computador. Usando o inicializador local.'
& (Join-Path $PSScriptRoot 'start-local-backend.ps1') -DatabasePath $DatabasePath -Port $Port
