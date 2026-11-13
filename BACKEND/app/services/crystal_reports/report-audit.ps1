function Get-ReportAudit {
    param($CurrentReport, [string]$Name)
    $formulas = @()
    for ($i=1; $i -le $CurrentReport.FormulaFields.Count; $i++) {
        $formula = $CurrentReport.FormulaFields.Item($i)
        $correct = $false
        $message = ''
        try { $formula.Check([ref]$correct, [ref]$message) }
        catch { $message = 'Falha ao compilar formula.' }
        $formulas += @{name=$formula.Name; compiled=$correct; message=[string]$message}
    }
    $fields = @()
    for ($i=1; $i -le $CurrentReport.Sections.Count; $i++) {
        $section = $CurrentReport.Sections.Item($i)
        for ($j=1; $j -le $section.ReportObjects.Count; $j++) {
            $object = $section.ReportObjects.Item($j)
            if ($object.Kind -eq 1 -or $object.Kind -eq 2) {
                $font = [DacteNative]::FontName($object.Font)
                $fields += @{object=$object.Name; field=[string]$object.Field.Name; font=$font;
                    left=$object.Left; top=$object.Top; width=$object.Width; height=$object.Height}
            }
        }
    }
    $credentialFields = @()
    for ($i=1; $i -le $CurrentReport.Database.Tables.Count; $i++) {
        $table = $CurrentReport.Database.Tables.Item($i)
        foreach ($property in $table.ConnectionProperties) {
            if ($property.Name -match '^(password|user ?id)$' -and [string]$property.Value) {
                $credentialFields += @{table=$table.Name; property=$property.Name}
            }
        }
    }
    return @{name=$Name; formulas=$formulas; fields=$fields; credential_fields=$credentialFields}
}

function Clear-ReportConnection {
    param($CurrentReport)
    $CurrentReport.DiscardSavedData()
    for ($i=1; $i -le $CurrentReport.Database.Tables.Count; $i++) {
        $table = $CurrentReport.Database.Tables.Item($i)
        foreach ($property in $table.ConnectionProperties) {
            if ($property.Name -match '^(password|user ?id|Data Source|Initial Catalog|PreQEServerName|PreQEDatabaseName|Integrated Security)$') {
                $property.Value = ''
            }
        }
    }
}
