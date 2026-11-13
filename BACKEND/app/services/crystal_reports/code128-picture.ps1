# Replace the access-key barcode presentation only in the opened report.
function Set-IndependentCode128Picture {
    param($CurrentReport, [string]$ImagePath, [bool]$AuditOnly = $false)
    if (!$AuditOnly -and ![IO.File]::Exists($ImagePath)) { throw 'Imagem Code 128 local ausente.' }
    $replaced = 0
    for ($i=1; $i -le $CurrentReport.Sections.Count; $i++) {
        $section = $CurrentReport.Sections.Item($i)
        $originalHeight = $section.Height
        $count = $section.ReportObjects.Count
        for ($j=1; $j -le $count; $j++) {
            $object = $section.ReportObjects.Item($j)
            if ($object.Kind -ne 1 -or [string]$object.Field.Name -ine '{@F_CODBAR}') { continue }
            $replaced++
            $suppressFormula = [string]$object.ConditionFormula(60)
            if (!$AuditOnly) {
                $picture = $section.AddPictureObject($ImagePath, $object.Left, $object.Top)
                $picture.Width = $object.Width
                $picture.Height = $object.Height
                $picture.Suppress = $object.Suppress
                # RDC 11.5 CRObjectFormatConditionFormulaType values, read from its type library.
                # Preserve conditional suppression and horizontal positioning/sizing.
                foreach ($formulaType in @(60,69,70)) {
                    $formula = [string]$object.ConditionFormula($formulaType)
                    if ($formula) {
                        [void]$picture.GetType().InvokeMember('ConditionFormula',
                            [Reflection.BindingFlags]::SetProperty, $null, $picture,
                            @([int]$formulaType, $formula))
                    }
                }
            }
            $object.Suppress = $true
            if ($suppressFormula) {
                [void]$object.GetType().InvokeMember('ConditionFormula',
                    [Reflection.BindingFlags]::SetProperty, $null, $object, @([int]60, 'True'))
            }
            $object.Font.Name = 'Arial'
        }
        $section.Height = $originalHeight
    }
    if ($replaced -eq 0) { throw 'RPT sem o campo F_CODBAR esperado; substituicao Code 128 recusada.' }
    return $replaced
}
