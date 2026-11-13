# Run in 32-bit Windows PowerShell. Credentials arrive through stdin, never argv.
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Console]::InputEncoding = New-Object System.Text.UTF8Encoding($false)
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$app = $null
$report = $null
$openedSubreports = New-Object System.Collections.ArrayList
$stage = 'request'
$operations = New-Object System.Collections.ArrayList
$qrCount = 0
$code128Count = 0
. (Join-Path $PSScriptRoot 'native-environment.ps1')
. (Join-Path $PSScriptRoot 'report-audit.ps1')
. (Join-Path $PSScriptRoot 'qr-picture.ps1')
. (Join-Path $PSScriptRoot 'code128-picture.ps1')

function Set-Stage {
    param([string]$Name)
    $script:stage = $Name
    [Console]::Error.WriteLine('CRYSTAL_STAGE=' + $Name)
}

function Open-CrystalApplication {
    param([string]$ProgId)
    $registry = [Microsoft.Win32.RegistryKey]::OpenBaseKey(
        [Microsoft.Win32.RegistryHive]::ClassesRoot,
        [Microsoft.Win32.RegistryView]::Registry32
    )
    try {
        $classKey = $registry.OpenSubKey($ProgId + '\CLSID')
        if ($null -eq $classKey) { throw 'Crystal Reports XI 32 bits nao esta registrado.' }
        $serverKey = $registry.OpenSubKey('CLSID\' + $classKey.GetValue('') + '\InprocServer32')
        if ($serverKey) {
            $engineDir = Split-Path -Parent $serverKey.GetValue('')
            $env:PATH = $engineDir + ';' + $env:PATH
            $serverKey.Dispose()
        }
        $classKey.Dispose()
    } finally { $registry.Dispose() }
    return New-Object -ComObject $ProgId
}

function Get-Subreports {
    param($ParentReport)
    for ($i = 1; $i -le $ParentReport.Sections.Count; $i++) {
        $section = $ParentReport.Sections.Item($i)
        for ($j = 1; $j -le $section.ReportObjects.Count; $j++) {
            $object = $section.ReportObjects.Item($j)
            if ($object.Kind -eq 5) {
                $subreport = $object.OpenSubreport()
                [void]$openedSubreports.Add($subreport)
                [pscustomobject]@{ Name = $object.SubreportName; Report = $subreport }
            }
        }
    }
}

function Get-ReportMetadata {
    param($CurrentReport, [string]$Name)
    $tables = @()
    for ($i = 1; $i -le $CurrentReport.Database.Tables.Count; $i++) {
        $table = $CurrentReport.Database.Tables.Item($i)
        $tables += [pscustomobject]@{
            name = $table.Name; location = $table.Location; driver = $table.DllName
        }
    }
    $parameters = @()
    for ($i = 1; $i -le $CurrentReport.ParameterFields.Count; $i++) {
        $parameter = $CurrentReport.ParameterFields.Item($i)
        $parameters += [pscustomobject]@{
            name = $parameter.Name; type = $parameter.ValueType; prompt = $parameter.Prompt
        }
    }
    $formulas = @()
    for ($i = 1; $i -le $CurrentReport.FormulaFields.Count; $i++) {
        $formula = $CurrentReport.FormulaFields.Item($i)
        $formulas += [pscustomobject]@{ name = $formula.Name; text = $formula.Text }
    }
    return [pscustomobject]@{
        name = $Name; tables = $tables; parameters = $parameters; formulas = $formulas
        selection = $CurrentReport.RecordSelectionFormula
    }
}

function Set-DatabaseConnection {
    param($CurrentReport, $Database)
    for ($i = 1; $i -le $CurrentReport.Database.Tables.Count; $i++) {
        Set-Stage ('database-table-' + $i)
        $table = $CurrentReport.Database.Tables.Item($i)
        $table.SetLogOnInfo(
            [string]$Database.server, [string]$Database.database,
            [string]$Database.user, [string]$Database.password
        )
        foreach ($property in $table.ConnectionProperties) {
            switch ($property.Name) {
                'Data Source' { $property.Value = [string]$Database.server }
                'Initial Catalog' { $property.Value = [string]$Database.database }
                'User ID' { $property.Value = [string]$Database.user }
                'Password' { $property.Value = [string]$Database.password }
                'Integrated Security' { $property.Value = $(if ($Database.auth -eq 'windows') { 'SSPI' } else { '' }) }
            }
        }
    }
}

try {
    $request = [Console]::In.ReadToEnd() | ConvertFrom-Json
    $request.prog_id = Resolve-CrystalProgId ([string]$request.prog_id)
    if ($request.action -notin @('inspect', 'export', 'environment', 'audit', 'package')) { throw 'Acao invalida.' }
    if ($request.action -eq 'environment') {
        $result = @{ok=$true; environment=(Get-CrystalEnvironment ([string]$request.prog_id))}
        [Console]::WriteLine('CRYSTAL_RESULT=' + ($result | ConvertTo-Json -Depth 16 -Compress))
        exit 0
    }
    Set-Stage 'engine'
    $app = Open-CrystalApplication ([string]$request.prog_id)
    Set-Stage 'report'
    $report = $app.OpenReport([string]$request.report_path, 1)
    [void]$operations.Add('OpenReport')
    $report.DisplayProgressDialog = $false
    $report.EnableParameterPrompting = $false
    $report.MorePrintEngineErrorMessages = $true
    $report.VerifyOnEveryPrint = $false
    $subreports = @(Get-Subreports $report)
    if ($request.qr_provider -eq 'python' -and $request.action -in @('audit', 'export')) {
        Set-Stage 'independent-qr'
        $qrCount = Set-IndependentQrPicture $report ([string]$request.qr_image_path) ($request.action -eq 'audit')
        if ($request.action -eq 'export') { [void]$operations.Add('AddPictureObject') }
    }
    if ($request.code128_provider -eq 'python' -and $request.action -in @('audit', 'export')) {
        Set-Stage 'independent-code128'
        $code128Count = Set-IndependentCode128Picture $report ([string]$request.code128_image_path) ($request.action -eq 'audit')
        if ($request.action -eq 'export') { [void]$operations.Add('AddPictureObject') }
    }
    if ($request.action -eq 'package') {
        Clear-ReportConnection $report
        foreach ($sub in $subreports) { Clear-ReportConnection $sub.Report }
        $report.Save([string]$request.output_path)
        $result = @{ok=$true; packaged=$true; has_saved_data=$report.HasSavedData}
    } elseif ($request.action -eq 'audit') {
        $result = @{ok=$true; reports=@((Get-ReportAudit $report 'main')) + @(
            $subreports | ForEach-Object { Get-ReportAudit $_.Report $_.Name })}
    } elseif ($request.action -eq 'inspect') {
        $result = [pscustomobject]@{
            ok = $true; engine = $request.prog_id; has_saved_data = $report.HasSavedData
            report = Get-ReportMetadata $report 'main'
            subreports = @($subreports | ForEach-Object { Get-ReportMetadata $_.Report $_.Name })
        }
    } else {
        # Discard before logon, and only when saved data actually exists.
        if ($report.HasSavedData) { $report.DiscardSavedData() }
        Set-Stage 'database'
        Set-DatabaseConnection $report $request.database
        foreach ($sub in $subreports) { Set-DatabaseConnection $sub.Report $request.database }
        Set-Stage 'parameters'
        $values = @{
            'P_CODFIL' = [double]$request.document.filial
            'P_SERCON' = [string]$request.document.serie
            'P_CODCON_INI' = [double]$request.document.documento
            'P_CODCON_FIN' = [double]$request.document.documento
        }
        $assigned = @()
        for ($i = 1; $i -le $report.ParameterFields.Count; $i++) {
            $parameter = $report.ParameterFields.Item($i)
            $name = $parameter.Name -replace '^\{\?', '' -replace '\}$', ''
            if (-not $values.ContainsKey($name)) { throw "Parametro nao previsto: $name" }
            $parameter.ClearCurrentValueAndRange()
            $parameter.AddCurrentValue($values[$name])
            $assigned += $name
        }
        foreach ($name in $values.Keys) {
            if ($name -notin $assigned) { throw "Parametro obrigatorio ausente: $name" }
        }
        Set-Stage 'records'
        $report.ReadRecords()
        [void]$operations.Add('ReadRecords')
        $recordCount = $report.PrintingStatus.NumberOfRecordRead
        if ($recordCount -eq 0) { throw 'Nenhum registro encontrado para este CTe.' }
        Set-Stage 'export'
        if ($request.pdf_engine -eq 'windows') {
            $printer = @(Get-CimInstance Win32_Printer -Filter "Name='Microsoft Print to PDF'" |
                Where-Object { $_.DriverName -eq 'Microsoft Print To PDF' })
            if ($printer.Count -ne 1) {
                throw 'Microsoft Print to PDF indisponivel. Ative o recurso PDF do Windows e repita o diagnostico.'
            }
            $report.SelectPrinter([string]$printer[0].DriverName, [string]$printer[0].Name, [string]$printer[0].PortName)
            # RDC requires a positive StopPage; use its maximum signed-short value.
            $report.PrintOutEx($false, 1, $false, 1, 32767, [string]$request.output_path)
            [void]$operations.Add('PrintOutEx')
            Set-Stage 'pdf-spooler'
            $complete = $false
            $deadline = [DateTime]::UtcNow.AddSeconds(30)
            while ([DateTime]::UtcNow -lt $deadline) {
                try {
                    $bytes = [IO.File]::ReadAllBytes([string]$request.output_path)
                    if ($bytes.Length -gt 5) {
                        $start = [Math]::Max(0, $bytes.Length - 1024)
                        $tail = [Text.Encoding]::ASCII.GetString($bytes, $start, $bytes.Length - $start)
                        if ([Text.Encoding]::ASCII.GetString($bytes, 0, 5) -eq '%PDF-' -and $tail.Contains('%%EOF')) {
                            $complete = $true
                            break
                        }
                    }
                } catch [IO.IOException] { }
                Start-Sleep -Milliseconds 200
            }
            if (!$complete) { throw 'A impressora virtual nao concluiu o arquivo PDF no prazo.' }
        } elseif ($request.pdf_engine -eq 'native') {
            $report.ExportOptions.DestinationType = 1 # crEDTDiskFile
            $report.ExportOptions.FormatType = 31 # crEFTPortableDocFormat
            $report.ExportOptions.PDFExportAllPages = $true
            $report.ExportOptions.DiskFileName = [string]$request.output_path
            $report.Export($false)
            [void]$operations.Add('ExportPDF')
        } else { throw 'Mecanismo PDF invalido.' }
        $result = [pscustomobject]@{
            ok = $true; engine = $request.prog_id; records = $recordCount
            output_path = $request.output_path
            execution_evidence = @{
                process_bits = [IntPtr]::Size * 8
                identity = [Security.Principal.WindowsIdentity]::GetCurrent().Name
                operations = @($operations); pictures_added = $qrCount + $code128Count; pdf_engine = $request.pdf_engine
                qr_pictures_added = $qrCount; code128_pictures_added = $code128Count
            }
        }
    }
    [Console]::WriteLine('CRYSTAL_RESULT=' + ($result | ConvertTo-Json -Depth 16 -Compress))
} catch {
    $message = $_.Exception.Message
    if ($request -and $request.database -and $request.database.password) {
        $message = $message.Replace([string]$request.database.password, '<redacted>')
    }
    [Console]::WriteLine('CRYSTAL_RESULT=' + (@{ok = $false; stage = $stage; error = $message} | ConvertTo-Json -Compress))
    exit 1
} finally {
    foreach ($sub in $openedSubreports) {
        if ([Runtime.InteropServices.Marshal]::IsComObject($sub)) {
            [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($sub)
        }
    }
    if ($report) { [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($report) }
    if ($app) { [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($app) }
}
