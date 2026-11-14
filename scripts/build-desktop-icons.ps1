param()

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$IconRoot = Join-Path $ProjectRoot 'FRONTEND-HUB\src-tauri\icons'
$PublicRoot = Join-Path $ProjectRoot 'FRONTEND-HUB\public'
$SourcePath = Join-Path $IconRoot 'app-icon-source.png'

# Package the source artwork into native Windows sizes without extra padding.
Add-Type -AssemblyName System.Drawing
$Source = [System.Drawing.Image]::FromFile($SourcePath)

function Convert-IconFrame([int]$Size) {
    $Bitmap = New-Object System.Drawing.Bitmap($Size, $Size, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
    $Graphics = [System.Drawing.Graphics]::FromImage($Bitmap)
    $Stream = New-Object System.IO.MemoryStream
    try {
        $Graphics.CompositingMode = [System.Drawing.Drawing2D.CompositingMode]::SourceCopy
        $Graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
        $Graphics.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
        $Graphics.Clear([System.Drawing.Color]::Transparent)
        $Graphics.DrawImage($Source, (New-Object System.Drawing.Rectangle(0, 0, $Size, $Size)))
        $Bitmap.Save($Stream, [System.Drawing.Imaging.ImageFormat]::Png)
        return ,$Stream.ToArray()
    } finally {
        $Stream.Dispose()
        $Graphics.Dispose()
        $Bitmap.Dispose()
    }
}

try {
    $Sizes = @(16, 20, 24, 32, 40, 48, 64, 96, 128, 256)
    $Frames = @{}
    foreach ($Size in $Sizes) { $Frames[$Size] = Convert-IconFrame $Size }
    $Output = New-Object System.IO.MemoryStream
    $Writer = New-Object System.IO.BinaryWriter($Output)
    try {
        $Writer.Write([uint16]0)
        $Writer.Write([uint16]1)
        $Writer.Write([uint16]$Sizes.Count)
        $Offset = 6 + 16 * $Sizes.Count
        foreach ($Size in $Sizes) {
            $Dimension = if ($Size -eq 256) { 0 } else { $Size }
            $Writer.Write([byte]$Dimension)
            $Writer.Write([byte]$Dimension)
            $Writer.Write([byte]0)
            $Writer.Write([byte]0)
            $Writer.Write([uint16]1)
            $Writer.Write([uint16]32)
            $Writer.Write([uint32]$Frames[$Size].Length)
            $Writer.Write([uint32]$Offset)
            $Offset += $Frames[$Size].Length
        }
        foreach ($Size in $Sizes) { $Writer.Write([byte[]]$Frames[$Size]) }
        $Writer.Flush()
        [System.IO.File]::WriteAllBytes((Join-Path $IconRoot 'icon.ico'), $Output.ToArray())
        [System.IO.File]::WriteAllBytes((Join-Path $PublicRoot 'favicon.ico'), $Output.ToArray())
    } finally {
        $Writer.Dispose()
        $Output.Dispose()
    }
    [System.IO.File]::WriteAllBytes((Join-Path $PublicRoot 'favicon-16x16.png'), $Frames[16])
    [System.IO.File]::WriteAllBytes((Join-Path $PublicRoot 'favicon-32x32.png'), $Frames[32])
    [System.IO.File]::WriteAllBytes((Join-Path $PublicRoot 'apple-touch-icon.png'), (Convert-IconFrame 180))
    Write-Host 'Icones Cargo Hub gerados em 10 resolucoes nativas, de 16 a 256 pixels.'
} finally {
    $Source.Dispose()
}
