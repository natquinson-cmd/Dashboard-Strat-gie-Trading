Add-Type -AssemblyName System.Drawing

# Resolve path dynamically to avoid encoding issues
$shapesFolder = (Get-ChildItem "C:\Users\quinson\Documents\Mon*Tableau\Formes\My shapes").FullName
$origPath = Join-Path $shapesFolder "KPI Box - Shadow.png"
Write-Host "Resolved path: $origPath"
Write-Host "File exists: $(Test-Path $origPath)"

# Get original dimensions
$orig = [System.Drawing.Image]::FromFile($origPath)
$w = $orig.Width
$h = $orig.Height
$orig.Dispose()
Write-Host "Original size: ${w}x${h}"

# Create dark KPI Box with same dimensions
$bmp = New-Object System.Drawing.Bitmap($w, $h)
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::HighQuality
$g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic

# Transparent background
$g.Clear([System.Drawing.Color]::Transparent)

# Colors
$cardColor = [System.Drawing.Color]::FromArgb(255, 17, 24, 39)        # #111827
$borderColor = [System.Drawing.Color]::FromArgb(200, 30, 42, 58)      # #1e2a3a
$shadowColor = [System.Drawing.Color]::FromArgb(80, 0, 0, 0)          # dark shadow
$glowColor = [System.Drawing.Color]::FromArgb(40, 99, 102, 241)       # #6366f1 subtle glow

# Margins for shadow area
$margin = [Math]::Max(15, [int]($w * 0.05))
$shadowOffset = [Math]::Max(4, [int]($w * 0.015))
$cornerRadius = [Math]::Max(20, [int]($w * 0.07))

# Helper function to create rounded rectangle path
function New-RoundedRectPath {
    param([int]$x, [int]$y, [int]$width, [int]$height, [int]$radius)
    $path = New-Object System.Drawing.Drawing2D.GraphicsPath
    $d = $radius * 2
    $path.AddArc($x, $y, $d, $d, 180, 90)
    $path.AddArc($x + $width - $d, $y, $d, $d, 270, 90)
    $path.AddArc($x + $width - $d, $y + $height - $d, $d, $d, 0, 90)
    $path.AddArc($x, $y + $height - $d, $d, $d, 90, 90)
    $path.CloseFigure()
    return $path
}

# Draw shadow (offset to bottom-right)
$shadowBrush = New-Object System.Drawing.SolidBrush($shadowColor)
$shadowPath = New-RoundedRectPath -x ($margin + $shadowOffset) -y ($margin + $shadowOffset) -width ($w - 2 * $margin) -height ($h - 2 * $margin) -radius $cornerRadius
$g.FillPath($shadowBrush, $shadowPath)
$shadowPath.Dispose()
$shadowBrush.Dispose()

# Draw subtle outer glow
$glowBrush = New-Object System.Drawing.SolidBrush($glowColor)
$glowPath = New-RoundedRectPath -x ($margin - 2) -y ($margin - 2) -width ($w - 2 * $margin + 4) -height ($h - 2 * $margin + 4) -radius ($cornerRadius + 2)
$g.FillPath($glowBrush, $glowPath)
$glowPath.Dispose()
$glowBrush.Dispose()

# Draw main card
$cardBrush = New-Object System.Drawing.SolidBrush($cardColor)
$cardPath = New-RoundedRectPath -x $margin -y $margin -width ($w - 2 * $margin) -height ($h - 2 * $margin) -radius $cornerRadius
$g.FillPath($cardBrush, $cardPath)

# Draw border
$borderPen = New-Object System.Drawing.Pen($borderColor, 2)
$g.DrawPath($borderPen, $cardPath)
$borderPen.Dispose()
$cardBrush.Dispose()
$cardPath.Dispose()

$g.Dispose()

# Backup original first
$backupPath = Join-Path $shapesFolder "KPI Box - Shadow - ORIGINAL.png"
if (-not (Test-Path $backupPath)) {
    Copy-Item $origPath $backupPath
    Write-Host "Backup saved: $backupPath"
}

# Save dark version over original
$bmp.Save($origPath, [System.Drawing.Imaging.ImageFormat]::Png)
Write-Host "Dark KPI Box saved to: $origPath"

# Also save a copy in the workbook Image folder
$wbCopy = "C:\Users\quinson\Desktop\Claude\Tableau DWH\twbx_extracted\Image\KPI Box - Shadow Dark.png"
$bmp.Save($wbCopy, [System.Drawing.Imaging.ImageFormat]::Png)
$bmp.Dispose()
Write-Host "Copy also saved to: $wbCopy"
Write-Host "Done!"
