$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $PSHOME 'Modules\Microsoft.PowerShell.Security') -ErrorAction Stop
$Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$File = Join-Path $Root 'BACKEND\.env'
if (!(Test-Path -LiteralPath $File -PathType Leaf)) { exit 1 }
try {
  $identity = [Security.Principal.WindowsIdentity]::GetCurrent().User
  $acl = New-Object Security.AccessControl.FileSecurity
  $acl.SetAccessRuleProtection($true, $false)
  $acl.SetOwner($identity)
  foreach ($sid in @($identity.Value, 'S-1-5-18', 'S-1-5-32-544')) {
    $account = New-Object Security.Principal.SecurityIdentifier($sid)
    $rule = New-Object Security.AccessControl.FileSystemAccessRule($account, 'FullControl', 'Allow')
    $acl.AddAccessRule($rule)
  }
  Set-Acl -LiteralPath $File -AclObject $acl
} catch { exit 1 }
exit 0
