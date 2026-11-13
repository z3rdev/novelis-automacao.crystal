$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $PSHOME 'Modules\Microsoft.PowerShell.Utility') -ErrorAction Stop
Import-Module (Join-Path $PSHOME 'Modules\Microsoft.PowerShell.Security') -ErrorAction Stop
$Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$Runtime = Join-Path $Root 'runtime'
New-Item -ItemType Directory -Force $Runtime | Out-Null
$ResultCode = 1
$result = [ordered]@{status='failed'; installed=$false; restart_required=$false}
function Get-WebViewVersion {
  $client = 'Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}'
  foreach ($key in @("HKLM:\SOFTWARE\WOW6432Node\$client", "HKCU:\Software\$client")) {
    $version = Get-ItemPropertyValue -LiteralPath $key -Name pv -ErrorAction SilentlyContinue
    if ($version -and $version -ne '0.0.0.0') { return [string]$version }
  }
  return ''
}
try {
  $version = Get-WebViewVersion
  if (!$version) {
    $folder = Join-Path $Root 'installer-cache\webview2'
    $manifest = Get-Content -LiteralPath (Join-Path $folder 'webview2.manifest.json') -Raw | ConvertFrom-Json
    if ($manifest.filename -ne 'MicrosoftEdgeWebView2RuntimeInstallerX64.exe') { throw 'Manifesto WebView2 invalido.' }
    $installer = Join-Path $folder $manifest.filename
    if ((Get-FileHash -LiteralPath $installer -Algorithm SHA256).Hash -ne $manifest.sha256) { throw 'Hash WebView2 invalido.' }
    $signature = Get-AuthenticodeSignature -LiteralPath $installer
    if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notlike '*Microsoft Corporation*') {
      throw 'Assinatura Microsoft WebView2 invalida.'
    }
    $process = Start-Process -FilePath $installer -ArgumentList '/silent','/install' -WindowStyle Hidden -Wait -PassThru
    $result.installer_exit_code = $process.ExitCode
    $result.restart_required = $process.ExitCode -in @(3010,1641)
    if ($process.ExitCode -notin @(0,3010,1641)) { throw 'Instalacao WebView2 falhou.' }
    $version = Get-WebViewVersion
    if (!$version) { throw 'WebView2 nao foi detectado apos instalacao.' }
    $result.installed = $true
  }
  $result.version = $version
  $result.status = 'succeeded'
  $ResultCode = 0
} catch { $result.error_type = $_.Exception.GetType().Name }
$result | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $Runtime 'webview2-result.json') -Encoding UTF8
Set-Content -LiteralPath (Join-Path $Runtime 'webview2-result.exitcode') -Value $ResultCode -Encoding ASCII
exit $ResultCode
