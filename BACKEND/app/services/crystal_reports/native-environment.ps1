# This module is loaded only by the isolated x86 worker.
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
[ComImport, Guid("BEF6E003-A874-101A-8BBA-00AA00300CAB"), InterfaceType(ComInterfaceType.InterfaceIsIDispatch)]
public interface DacteFontDisp { [DispId(0)] string Name { get; } }
public static class DacteNative {
    [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
    public static extern IntPtr LoadLibraryEx(string path, IntPtr file, uint flags);
    [DllImport("kernel32.dll")] public static extern bool FreeLibrary(IntPtr module);
    public static string FontName(object font) { return ((DacteFontDisp)font).Name; }
}
'@

function Get-PeMachine {
    param([string]$Path)
    $bytes = [IO.File]::ReadAllBytes($Path)
    if ($bytes.Length -lt 64 -or $bytes[0] -ne 77 -or $bytes[1] -ne 90) { return 'invalid' }
    $offset = [BitConverter]::ToInt32($bytes, 60)
    if ($offset -lt 0 -or $offset + 6 -gt $bytes.Length) { return 'invalid' }
    if ([BitConverter]::ToUInt32($bytes, $offset) -ne 17744) { return 'invalid' }
    switch ([BitConverter]::ToUInt16($bytes, $offset + 4)) {
        332 { return 'x86' }
        34404 { return 'x64' }
        43620 { return 'arm64' }
        default { return 'unknown' }
    }
}

function Get-ComServerPath {
    param([string]$ProgId)
    $registry = [Microsoft.Win32.RegistryKey]::OpenBaseKey(
        [Microsoft.Win32.RegistryHive]::ClassesRoot, [Microsoft.Win32.RegistryView]::Registry32)
    try {
        $key = $registry.OpenSubKey($ProgId + '\CLSID')
        if (!$key) { return '' }
        $server = $registry.OpenSubKey('CLSID\' + $key.GetValue('') + '\InprocServer32')
        $key.Dispose()
        if (!$server) { return '' }
        try { return [string]$server.GetValue('') } finally { $server.Dispose() }
    } finally { $registry.Dispose() }
}

function Test-NativeDll {
    param([string]$Path)
    $exists = [bool]($Path -and (Test-Path -LiteralPath $Path -PathType Leaf))
    $machine = if ($exists) { Get-PeMachine $Path } else { 'missing' }
    $loaded = $false
    $loadError = 0
    $version = ''
    if ($exists) { $version = (Get-Item -LiteralPath $Path).VersionInfo.FileVersion }
    if ($machine -eq 'x86') {
        $handle = [DacteNative]::LoadLibraryEx($Path, [IntPtr]::Zero, 8)
        if ($handle -eq [IntPtr]::Zero) { $loadError = [Runtime.InteropServices.Marshal]::GetLastWin32Error() }
        else { $loaded = $true; [void][DacteNative]::FreeLibrary($handle) }
    }
    return [pscustomobject]@{path=$Path; exists=$exists; architecture=$machine;
        version=$version; loadable=$loaded; win32_error=$loadError}
}

function Resolve-CrystalProgId {
    param([string]$Configured)
    if ($Configured) { return $Configured }
    return 'CrystalDesignRunTime.Application.11'
}

function Get-CrystalEnvironment {
    param([string]$ProgId)
    $engine = Get-ComServerPath $ProgId
    $engineDir = if ($engine) { Split-Path -Parent $engine } else { '' }
    if ($engineDir) { $env:PATH = $engineDir + ';' + $env:PATH }
    $native = @()
    foreach ($name in @('crpe32.dll', 'crdb_ado.dll', 'u2lcom.dll', 'crxf_pdf.dll')) {
        $path = if ($engineDir) { Join-Path $engineDir $name } else { '' }
        $native += Test-NativeDll $path
    }
    $engineInfo = Test-NativeDll $engine
    $comCreated = $false; $providerCreated = $false
    $application = $null; $provider = $null
    try { $application = New-Object -ComObject $ProgId; $comCreated = $true } catch { }
    finally { if ($application) { [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($application) } }
    try {
        $provider = [Activator]::CreateInstance([Type]::GetTypeFromProgID('SQLOLEDB', $true))
        $providerCreated = $true
    } catch { }
    finally { if ($provider) { [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($provider) } }
    $bcsPath = Get-ComServerPath 'cruflBCS.QRCode'
    if (!$bcsPath) {
        $bcsPath = Join-Path ([Environment]::GetFolderPath('CommonProgramFilesX86')) 'Barcodesoft\FontUtil\cruflbcs.dll'
    }
    $bcs = Test-NativeDll $bcsPath
    $bcs | Add-Member -NotePropertyName registered -NotePropertyValue ([bool](Get-ComServerPath 'cruflBCS.QRCode'))
    $bcsFunctions = @{available=$false; functions=@()}
    $qr = $null
    try {
        if ($bcs.registered -and $bcs.architecture -eq 'x86') {
            $qr = New-Object -ComObject cruflBCS.QRCode
            $segments = $qr.FormulaNoForCR('DACTE-DIAGNOSTIC')
            $encoded = $qr.EncodeCR('DACTE-DIAGNOSTIC', 1, 2)
            $bcsFunctions = @{available=($segments -ge 1 -and $encoded.Length -gt 0);
                functions=@('BCSQRCodeFormulaNoForCR','BCSQRCodeEncodeCR')}
        }
    } catch { $bcsFunctions.error = 'Nao foi possivel executar as funcoes BCS em x86.' }
    finally { if ($qr) { [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($qr) } }
    Add-Type -AssemblyName System.Drawing
    $collection = New-Object System.Drawing.Text.InstalledFontCollection
    try { $fonts = @($collection.Families | ForEach-Object { $_.Name }) }
    finally { $collection.Dispose() }
    $currentVersion = Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion'
    $pdfPrinter = @(Get-CimInstance Win32_Printer -Filter "Name='Microsoft Print to PDF'" |
        Where-Object { $_.DriverName -eq 'Microsoft Print To PDF' })
    return [pscustomobject]@{
        process_bits=([IntPtr]::Size * 8); os_build=$currentVersion.CurrentBuildNumber
        engine=$engineInfo; prog_id=$ProgId
        compatible=($comCreated -and $providerCreated -and $engineInfo.loadable -and $engineInfo.architecture -eq 'x86' -and $engineInfo.version -like '11.5.*')
        com_created=$comCreated; sqloledb_x86_created=$providerCreated
        native_dlls=$native; barcodesoft=$bcs; bcs_functions=$bcsFunctions
        fonts=$fonts; compatibility_note='Crystal XI R2 e legado; os testes locais nao certificam suporte do fabricante ao Windows 10/11.'
        windows_pdf_printer_available=($pdfPrinter.Count -eq 1)
    }
}
