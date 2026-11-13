# Replace only QR presentation in the opened report. Never save changes to the RPT.
function Set-IndependentQrPicture {
    param($CurrentReport, [string]$ImagePath, [bool]$AuditOnly = $false)
    if (!$AuditOnly -and ![IO.File]::Exists($ImagePath)) { throw 'Imagem QR local ausente.' }
    $replaced = 0
    for ($i=1; $i -le $CurrentReport.Sections.Count; $i++) {
        $section = $CurrentReport.Sections.Item($i)
        $originalHeight = $section.Height
        # Freeze the original count because AddPictureObject changes this collection.
        $count = $section.ReportObjects.Count
        for ($j=1; $j -le $count; $j++) {
            $object = $section.ReportObjects.Item($j)
            if ($object.Kind -ne 1 -or [string]$object.Field.Name -ine '{@F_QRCODE}') { continue }
            $replaced++
            if (!$AuditOnly) {
                $size = [Math]::Min($object.Width, $object.Height)
                $picture = $section.AddPictureObject($ImagePath, $object.Left, $object.Top)
                $picture.Width = $size
                $picture.Height = $size
                $picture.Suppress = $object.Suppress
            }
            $object.Suppress = $true
            # No barcode font is needed for the suppressed, empty field.
            $object.Font.Name = 'Arial'
        }
        # Adding the high-resolution bitmap initially expands the section to its
        # pixel size. Restore the saved height after sizing the picture in twips.
        $section.Height = $originalHeight
    }
    if ($replaced -eq 0) { throw 'RPT sem o campo F_QRCODE esperado; substituicao QR recusada.' }
    foreach ($formula in $CurrentReport.FormulaFields) {
        if ($formula.Name -iin @('{@F_QRCODE}', '{@qrcode}')) {
            # These are presentation encoders only. Original formulas remain on disk.
            # RDC's Text setter uses Crystal syntax, even for a saved Basic formula.
            $formula.Text = '""'
        }
    }
    return $replaced
}
