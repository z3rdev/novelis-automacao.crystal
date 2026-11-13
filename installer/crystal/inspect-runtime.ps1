param([string]$OutputPath = '')
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'runtime-probe.ps1')
try {
    $result = Get-RdcRuntimeState
    $json = $result | ConvertTo-Json -Depth 8
    if ($OutputPath) {
        [IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName([IO.Path]::GetFullPath($OutputPath))) | Out-Null
        [IO.File]::WriteAllText($OutputPath, $json, [Text.UTF8Encoding]::new($false))
    }
    [Console]::WriteLine('CRYSTAL_PROBE=' + ($result | ConvertTo-Json -Depth 8 -Compress))
    if ($result.functional) { exit 0 } else { exit 2 }
} catch {
    [Console]::WriteLine('CRYSTAL_PROBE={"functional":false,"error":"Falha no diagnostico x86","production_ready":false}')
    exit 2
}
