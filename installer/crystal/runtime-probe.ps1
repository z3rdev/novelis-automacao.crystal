# Shared by the isolated x86 probe and the Inno prerequisite stage. Never reads keycodes.
function Get-RdcRuntimeState {
    param([string]$ExpectedVersion = '11.5.0.313')
    if ([IntPtr]::Size -ne 4) { throw 'O diagnostico RDC deve executar em processo x86.' }
    Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class NovelisRdcLoader {
 [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
 public static extern IntPtr LoadLibraryEx(string path, IntPtr file, uint flags);
 [DllImport("kernel32.dll")] public static extern bool FreeLibrary(IntPtr module);
 [DllImport("msi.dll", CharSet=CharSet.Unicode)]
 public static extern int MsiQueryProductState(string product);
 [DllImport("msi.dll", CharSet=CharSet.Unicode)]
 public static extern int MsiQueryFeatureState(string product, string feature);
 [DllImport("msi.dll", CharSet=CharSet.Unicode)]
 public static extern int MsiGetComponentPath(string product, string component, System.Text.StringBuilder path, ref uint size);
}
'@
    $installerProducts = @()
    foreach ($product in @(
        @{version='1.0.0';code='{91BD5684-A33F-516A-996C-38D91FBF0A02}'},
        @{version='1.0.1';code='{292A5FD3-7C11-5197-9685-CBC0CADF4CF5}'},
        @{version='1.0.2';code='{CF1D3AFB-ADE5-5960-AA9D-27928364A854}'})) {
        $installerProducts += [pscustomobject]@{version=$product.version;product_code=$product.code;
            product_state=[NovelisRdcLoader]::MsiQueryProductState($product.code);
            feature_state=[NovelisRdcLoader]::MsiQueryFeatureState($product.code,'CrystalRDC')}
    }
    $components = @{
        'craxddrt.dll'='{AC0F7C51-52A0-40AE-B8EF-019B4D80E7D1}'
        'crpe32.dll'='{CBCED3BD-3BB0-4636-B93E-DD128E8348F6}'
        'crdb_ado.dll'='{F529A017-B43B-4650-AF30-5060E7964F81}'
        'u2lcom.dll'='{BA6001D2-2575-4B5B-B281-1995A1E69303}'
        'crxf_pdf.dll'='{80A0691C-63CB-4A09-9FC1-C326C8CEE28E}'
    }
    $componentPaths = @{}
    foreach ($name in $components.Keys) {
        foreach ($product in $installerProducts) {
            $buffer = New-Object Text.StringBuilder 32768
            [uint32]$size = 32768
            $state = [NovelisRdcLoader]::MsiGetComponentPath($product.product_code,$components[$name],$buffer,[ref]$size)
            if ($state -ge 0 -and $buffer.Length -gt 0) {
                $componentPaths[$name] = [pscustomobject]@{state=$state;path=$buffer.ToString()}; break
            }
        }
    }
    $registry = [Microsoft.Win32.RegistryKey]::OpenBaseKey(
        [Microsoft.Win32.RegistryHive]::ClassesRoot, [Microsoft.Win32.RegistryView]::Registry32)
    $path = ''
    $anyCrystal = $false
    try {
        foreach ($id in @('CrystalRuntime.Application.11', 'CrystalDesignRunTime.Application.11')) {
            $key = $registry.OpenSubKey($id + '\CLSID')
            if ($key) {
                $anyCrystal = $true
                if ($id -eq 'CrystalDesignRunTime.Application.11') {
                    $server = $registry.OpenSubKey('CLSID\' + $key.GetValue('') + '\InprocServer32')
                    if ($server) { $path = [string]$server.GetValue(''); $server.Dispose() }
                }
                $key.Dispose()
            }
        }
    } finally { $registry.Dispose() }
    $pathSource = if ($path) { 'com_registry' } else { 'not_resolved' }
    if (!$path -and $componentPaths.ContainsKey('craxddrt.dll')) {
        $path = $componentPaths['craxddrt.dll'].path
        $pathSource = 'windows_installer_component'
    }
    $directory = if ($path) { Split-Path -Parent $path } else { '' }
    if ($directory) { $env:PATH = $directory + ';' + $env:PATH }
    $dlls = @()
    foreach ($name in @('craxddrt.dll','crpe32.dll','crdb_ado.dll','u2lcom.dll','crxf_pdf.dll')) {
        $file = if ($directory) { Join-Path $directory $name } else { '' }
        if ($componentPaths.ContainsKey($name)) { $file = $componentPaths[$name].path }
        $exists = [bool]($file -and (Test-Path -LiteralPath $file -PathType Leaf))
        $version = ''; $x86 = $false; $loadable = $false; $loadError = 0
        if ($exists) {
            $bytes = [IO.File]::ReadAllBytes($file)
            if ($bytes.Length -ge 64 -and $bytes[0] -eq 77 -and $bytes[1] -eq 90) {
                $offset = [BitConverter]::ToInt32($bytes,60)
                $x86 = $offset -ge 0 -and $offset+6 -le $bytes.Length -and
                    [BitConverter]::ToUInt32($bytes,$offset) -eq 17744 -and
                    [BitConverter]::ToUInt16($bytes,$offset+4) -eq 332
            }
            $version = (Get-Item -LiteralPath $file).VersionInfo.FileVersion
            if ($x86) {
                $handle = [NovelisRdcLoader]::LoadLibraryEx($file,[IntPtr]::Zero,8)
                $loadable = $handle -ne [IntPtr]::Zero
                if ($loadable) { [void][NovelisRdcLoader]::FreeLibrary($handle) }
                else { $loadError = [Runtime.InteropServices.Marshal]::GetLastWin32Error() }
            }
        }
        $dlls += [pscustomobject]@{name=$name;path=$file;exists=$exists;version=$version;
            x86=$x86;loadable=$loadable;win32_error=$loadError}
    }
    $comCreated = $false; $comHresult = ''; $providerCreated = $false; $application = $null; $provider = $null
    try { $application = New-Object -ComObject CrystalDesignRunTime.Application.11; $comCreated = $true }
    catch { $comHresult = '0x' + $_.Exception.GetBaseException().HResult.ToString('X8') }
    finally { if ($application) { [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($application) } }
    try {
        $type = [Type]::GetTypeFromProgID('SQLOLEDB', $true)
        $provider = [Activator]::CreateInstance($type); $providerCreated = $true
    } catch { }
    finally { if ($provider) { [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($provider) } }
    $products = @()
    foreach ($view in @([Microsoft.Win32.RegistryView]::Registry32,[Microsoft.Win32.RegistryView]::Registry64)) {
        $base = [Microsoft.Win32.RegistryKey]::OpenBaseKey([Microsoft.Win32.RegistryHive]::LocalMachine,$view)
        try {
            $uninstall = $base.OpenSubKey('SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall')
            if ($uninstall) {
                foreach ($name in $uninstall.GetSubKeyNames()) {
                    $item = $uninstall.OpenSubKey($name)
                    try {
                        $display = [string]$item.GetValue('DisplayName')
                        if ($display -match 'Crystal Reports|Crystal Runtime|Novelis Crystal RDC') {
                            $products += [pscustomobject]@{name=$display;version=[string]$item.GetValue('DisplayVersion')}
                        }
                    } finally { $item.Dispose() }
                }
                $uninstall.Dispose()
            }
        } finally { $base.Dispose() }
    }
    $fullEditor = (Test-Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\{94FB0978-D094-40C7-91D7-834D39220D4A}')
    $machine = (Get-CimInstance Win32_ComputerSystemProduct).UUID
    $boot = (Get-CimInstance Win32_OperatingSystem).LastBootUpTime.ToUniversalTime().ToString('o')
    return [pscustomobject]@{
        schema_version=1; process_bits=32; prog_id='CrystalDesignRunTime.Application.11'
        identity=[Security.Principal.WindowsIdentity]::GetCurrent().Name
        computer=$env:COMPUTERNAME; machine_uuid=$machine; last_boot_utc=$boot
        checked_at=[DateTime]::UtcNow.ToString('o'); installed_crystal_products=$products
        expected_version=$ExpectedVersion
        any_crystal_registered=$anyCrystal; com_created=$comCreated; sqloledb_x86_created=$providerCreated
        com_hresult=$comHresult; dll_path_source=$pathSource
        installer_products=$installerProducts; component_paths=$componentPaths
        full_editor_installed=[bool]$fullEditor; dlls=$dlls
        functional=($comCreated -and $providerCreated -and
            @($dlls | Where-Object {!$_.loadable -or !$_.x86 -or $_.version -ne $ExpectedVersion}).Count -eq 0)
        rcapi_export_tested=$false; production_ready=$false
    }
}
