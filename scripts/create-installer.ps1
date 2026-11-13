param([string]$Version = '', [ValidateSet('development','distribution')][string]$BuildMode = 'distribution',
      [Parameter(Mandatory=$true)][string]$CrystalManifest, [string]$CrystalApproval = '',
      [ValidatePattern('^(r[1-9][0-9]*)?$')][string]$InstallerRevision = '',
      [string]$OperationalEnvPath = '')
$ErrorActionPreference = 'Stop'
$buildScript = Join-Path $PSScriptRoot 'build-installer.ps1'
$buildArguments = @{BuildMode=$BuildMode; CrystalManifest=$CrystalManifest}
if ($Version) { $buildArguments.Version = $Version }
if ($CrystalApproval) { $buildArguments.CrystalApproval = $CrystalApproval }
if ($InstallerRevision) { $buildArguments.InstallerRevision = $InstallerRevision }
if ($OperationalEnvPath) { $buildArguments.OperationalEnvPath = $OperationalEnvPath }
& $buildScript @buildArguments
exit $LASTEXITCODE
