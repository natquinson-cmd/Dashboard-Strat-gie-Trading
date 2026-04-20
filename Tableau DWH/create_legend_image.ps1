Add-Type -AssemblyName System.Drawing

# Build the legend image
$width = 440
$height = 320
$bmp = New-Object System.Drawing.Bitmap($width, $height, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
$g.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::ClearTypeGridFit
$g.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
$g.Clear([System.Drawing.Color]::White)

# Items to draw
$items = @(
    @{ Label = 'Termin' + [char]0xE9; Color = [System.Drawing.Color]::FromArgb(89, 161, 79) },
    @{ Label = 'En cours'; Color = [System.Drawing.Color]::FromArgb(246, 165, 92) },
    @{ Label = 'Tests en cours'; Color = [System.Drawing.Color]::FromArgb(242, 142, 43) },
    @{ Label = 'Analyse en cours'; Color = [System.Drawing.Color]::FromArgb(241, 206, 99) },
    @{ Label = 'R' + [char]0xE9 + 'alisation en cours'; Color = [System.Drawing.Color]::FromArgb(252, 180, 109) },
    @{ Label = 'Pr' + [char]0xEA + 't pour r' + [char]0xE9 + 'alisation'; Color = [System.Drawing.Color]::FromArgb(255, 190, 125) },
    @{ Label = 'A faire'; Color = [System.Drawing.Color]::FromArgb(89, 89, 89) },
    @{ Label = 'NULL'; Color = [System.Drawing.Color]::FromArgb(213, 213, 213) }
)

$font = New-Object System.Drawing.Font('Tableau Book', 14, [System.Drawing.FontStyle]::Regular)
if ($null -eq $font) {
    $font = New-Object System.Drawing.Font('Segoe UI', 14, [System.Drawing.FontStyle]::Regular)
}
$textBrush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(50, 50, 50))
$borderPen = New-Object System.Drawing.Pen([System.Drawing.Color]::FromArgb(80, 0, 0, 0), 1)

$padding = 12
$rowHeight = 36
$squareSize = 20
$squareX = $padding
$textX = $padding + $squareSize + 12
$startY = $padding

for ($i = 0; $i -lt $items.Count; $i++) {
    $y = $startY + $i * $rowHeight
    # Color square
    $brush = New-Object System.Drawing.SolidBrush($items[$i].Color)
    $g.FillRectangle($brush, [int]$squareX, [int]($y + 4), [int]$squareSize, [int]$squareSize)
    $g.DrawRectangle($borderPen, [int]$squareX, [int]($y + 4), [int]$squareSize, [int]$squareSize)
    $brush.Dispose()
    # Text
    $g.DrawString($items[$i].Label, $font, $textBrush, [single]$textX, [single]($y + 4))
}

$borderPen.Dispose()
$textBrush.Dispose()
$font.Dispose()
$g.Dispose()

$out = 'C:\Users\quinson\Desktop\Claude\Tableau DWH\Legende_Statut.png'
$bmp.Save($out, [System.Drawing.Imaging.ImageFormat]::Png)
$bmp.Dispose()
Write-Host "Saved: $out ($width x $height)"
