param(
    [Parameter(Mandatory=$true)][string]$ManifestPath,
    [switch]$AllowDevelopment,
    [ValidateSet('Install','Repair')][string]$Action = 'Install',
    [string]$ResultPath = '',
    [string]$ProbeDirectory = ''
)
$ErrorActionPreference = 'Stop'
$exitCode = 2
$result = [ordered]@{schema_version=1;status='failed';stage='manifest';production_ready=$false}
try {
    $manifestFile = (Resolve-Path -LiteralPath $ManifestPath).Path
    $manifest = Get-Content -LiteralPath $manifestFile -Raw -Encoding UTF8 | ConvertFrom-Json
    if ([IO.Path]::GetFileName($manifest.filename) -ne $manifest.filename) { throw 'Caminho MSI invalido.' }
    $msi = Join-Path (Split-Path -Parent $manifestFile) $manifest.filename
    if ($manifest.runtime_version -ne '11.5.0.313' -or $manifest.architecture -ne 'x86' -or
        !$manifest.structure_verified -or !$manifest.audit.execute_sequence_verified -or $manifest.withdrawn -or
        (Get-FileHash -LiteralPath $msi -Algorithm SHA256).Hash -ne $manifest.sha256) {
        throw 'Integridade/estrutura do MSI nao comprovada.'
    }
    $result.stage = 'authorization'
    if ($manifest.build_mode -eq 'development') {
        if (!$AllowDevelopment) { throw 'Pacote de desenvolvimento requer teste explicitamente autorizado.' }
    } elseif ($manifest.build_mode -ne 'distribution' -or !$manifest.redistribution_approved) {
        throw 'Distribuicao do MSI nao autorizada.'
    }
    if (!$ProbeDirectory) {
        $ProbeDirectory = Join-Path (Split-Path -Parent $PSScriptRoot) 'installer\crystal'
    }
    $ps32 = Join-Path $env:SystemRoot 'SysWOW64\WindowsPowerShell\v1.0\powershell.exe'
    function Invoke-RuntimeProbe {
        $lines = & $ps32 -NoProfile -NonInteractive -STA -ExecutionPolicy Bypass -File (Join-Path $ProbeDirectory 'inspect-runtime.ps1')
        $line = $lines | Where-Object { $_ -like 'CRYSTAL_PROBE=*' } | Select-Object -Last 1
        if (!$line) { throw 'Diagnostico sem resposta.' }
        return $line.Substring(14) | ConvertFrom-Json
    }
    $result.stage = 'probe_before'
    $before = Invoke-RuntimeProbe
    $result.before = $before
    $result.package_sha256 = $manifest.sha256
    $result.action = $Action
    if ($before.functional -and $Action -eq 'Install') {
        $result.status = 'already_functional'; $exitCode = 0
    } else {
        $result.stage = 'elevation'
        $principal = [Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())
        if (!$principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
            $result.status = 'needs_elevation'; $exitCode = 740
        } else {
            $result.stage = 'logging_policy'
            # A system-wide verbose/debug logging policy can expose legacy vendor custom actions.
            # Do not alter that policy; require the test VM administrator to resolve it.
            $loggingPolicy = Get-ItemProperty 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\Installer' -ErrorAction SilentlyContinue
            if ($loggingPolicy.Logging -or $loggingPolicy.Debug) {
                throw 'Politica global de log MSI exige revisao antes do teste com PIDKEY.'
            }
            # Only event summaries are logged. No PIDKEY on argv and no verbose MSI log.
            $arguments = '/i "' + $msi + '" /qn /norestart'
            $productCode = [string]$manifest.audit.product_code
            $productInstalled = Test-Path ('HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\' + $productCode)
            $productInstalled = $productInstalled -or (Test-Path ('HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\' + $productCode))
            if ($Action -eq 'Repair' -or $productInstalled) { $arguments += ' REINSTALL=ALL REINSTALLMODE=vomus' }
            if ($AllowDevelopment -and $manifest.build_mode -eq 'development') { $arguments += ' NOVELIS_DEVELOPMENT_TEST=1' }
            $result.stage = 'msiexec'
            $process = Start-Process -FilePath (Join-Path $env:SystemRoot 'System32\msiexec.exe') -ArgumentList $arguments -WindowStyle Hidden -Wait -PassThru
            $result.msi_exit_code = $process.ExitCode
            $result.package_sha256 = $manifest.sha256
            if ($process.ExitCode -in @(3010,1641)) { $result.status = 'restart_required'; $exitCode = 3010 }
            elseif ($process.ExitCode -eq 1618) { $result.status = 'another_installation_running'; $exitCode = 1618 }
            elseif ($process.ExitCode -ne 0) { $result.status = 'msi_failed'; $exitCode = $process.ExitCode }
            else {
                $result.stage = 'probe_after'
                $result.after = Invoke-RuntimeProbe
                if ($result.after.functional) { $result.status = 'installed_verified'; $exitCode = 0 }
                else { $result.status = 'post_install_failed'; $exitCode = 2 }
            }
        }
    }
} catch {
    # Avoid serial-bearing custom-action exceptions in unattended logs.
    $result.status = 'validation_failed'; $exitCode = 2
}
$result.exit_code = $exitCode
$result.checked_at = [DateTime]::UtcNow.ToString('o')
if ($ResultPath) {
    [IO.Directory]::CreateDirectory((Split-Path -Parent ([IO.Path]::GetFullPath($ResultPath)))) | Out-Null
    [IO.File]::WriteAllText($ResultPath, ($result | ConvertTo-Json -Depth 12), [Text.UTF8Encoding]::new($false))
    [IO.File]::WriteAllText($ResultPath + '.exitcode', [string]$exitCode, [Text.UTF8Encoding]::new($false))
}
[Console]::WriteLine('CRYSTAL_INSTALL=' + ($result | ConvertTo-Json -Depth 12 -Compress))
exit $exitCode
