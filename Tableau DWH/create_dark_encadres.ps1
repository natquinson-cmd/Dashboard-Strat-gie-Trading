Add-Type -AssemblyName System.Drawing

$imageFolder = "C:\Users\quinson\Desktop\Claude\Tableau DWH\twbx_extracted\Image"

# Frame definitions: name => width, height
$frames = @(
    @{ Name = "Encadré Haut Gauche Page1.png"; W = 534; H = 237 },
    @{ Name = "Encadré Haut Milieu Page1.png"; W = 315; H = 225 },
    @{ Name = "Encadré Haut Droite Page1.png"; W = 408; H = 377 },
    @{ Name = "Encadré milieu Page 1.png"; W = 1365; H = 226 },
    @{ Name = "Encadré bas gauche Page1.png"; W = 1268; H = 319 },
    @{ Name = "Encadré bas droite Page1.png"; W = 487; H = 323 }
)

# Colors
$cardColor = [System.Drawing.Color]::FromArgb(255, 17, 24, 39)        # #111827
$borderColor = [System.Drawing.Color]::FromArgb(180, 30, 42, 58)      # #1e2a3a
$shadowColor = [System.Drawing.Color]::FromArgb(60, 0, 0, 0)          # dark shadow
$glowColor = [System.Drawing.Color]::FromArgb(25, 99, 102, 241)       # #6366f1 subtle glow
$headerColor = [System.Drawing.Color]::FromArgb(255, 22, 30, 48)      # slightly lighter header

# Helper function to create rounded rectangle path
function New-RoundedRectPath {
    param([int]$x, [int]$y, [int]$width, [int]$height, [int]$radius)
    $path = New-Object System.Drawing.Drawing2D.GraphicsPath
    $d = $radius * 2
    # Clamp radius if too large for the rect
    if ($d -gt $width) { $d = $width; $radius = [int]($d / 2) }
    if ($d -gt $height) { $d = $height; $radius = [int]($d / 2) }
    $path.AddArc($x, $y, $d, $d, 180, 90)
    $path.AddArc($x + $width - $d, $y, $d, $d, 270, 90)
    $path.AddArc($x + $width - $d, $y + $height - $d, $d, $d, 0, 90)
    $path.AddArc($x, $y + $height - $d, $d, $d, 90, 90)
    $path.CloseFigure()
    return $path
}

foreach ($frame in $frames) {
    $w = $frame.W
    $h = $frame.H
    $name = $frame.Name
    $filePath = Join-Path $imageFolder $name

    Write-Host "Creating: $name (${w}x${h})"

    # Backup original
    $backupPath = Join-Path $imageFolder ($name -replace '\.png$', ' - ORIGINAL.png')
    if (-not (Test-Path $backupPath)) {
        if (Test-Path $filePath) {
            Copy-Item $filePath $backupPath
            Write-Host "  Backup: $backupPath"
        }
    }

    $bmp = New-Object System.Drawing.Bitmap($w, $h, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::HighQuality
    $g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic

    # Transparent background
    $g.Clear([System.Drawing.Color]::Transparent)

    # Calculate proportional values
    $margin = [Math]::Max(8, [int]([Math]::Min($w, $h) * 0.03))
    $shadowOffset = [Math]::Max(3, [int]([Math]::Min($w, $h) * 0.012))
    $cornerRadius = [Math]::Max(12, [int]([Math]::Min($w, $h) * 0.05))
    $headerHeight = [Math]::Max(4, [int]($h * 0.015))
    $borderWidth = [Math]::Max(1.0, [Math]::Min(2.0, $w * 0.003))

    $rectX = $margin
    $rectY = $margin
    $rectW = $w - 2 * $margin
    $rectH = $h - 2 * $margin

    # 1. Draw shadow (offset bottom-right)
    $shadowBrush = New-Object System.Drawing.SolidBrush($shadowColor)
    $shadowPath = New-RoundedRectPath -x ($rectX + $shadowOffset) -y ($rectY + $shadowOffset) -width $rectW -height $rectH -radius $cornerRadius
    $g.FillPath($shadowBrush, $shadowPath)
    $shadowPath.Dispose()
    $shadowBrush.Dispose()

    # 2. Draw subtle outer glow
    $glowBrush = New-Object System.Drawing.SolidBrush($glowColor)
    $glowPath = New-RoundedRectPath -x ($rectX - 1) -y ($rectY - 1) -width ($rectW + 2) -height ($rectH + 2) -radius ($cornerRadius + 1)
    $g.FillPath($glowBrush, $glowPath)
    $glowPath.Dispose()
    $glowBrush.Dispose()

    # 3. Draw main card body
    $cardBrush = New-Object System.Drawing.SolidBrush($cardColor)
    $cardPath = New-RoundedRectPath -x $rectX -y $rectY -width $rectW -height $rectH -radius $cornerRadius
    $g.FillPath($cardBrush, $cardPath)
    $cardBrush.Dispose()

    # 4. Draw subtle header gradient at top
    $headerRect = New-Object System.Drawing.Rectangle($rectX + $cornerRadius, $rectY, $rectW - 2 * $cornerRadius, $headerHeight)
    if ($headerRect.Width -gt 0 -and $headerRect.Height -gt 0) {
        $headerBrush = New-Object System.Drawing.SolidBrush($headerColor)
        $g.FillRectangle($headerBrush, $headerRect)
        $headerBrush.Dispose()
    }

    # 5. Draw top accent line (subtle indigo)
    $accentColor = [System.Drawing.Color]::FromArgb(40, 99, 102, 241)
    $accentPen = New-Object System.Drawing.Pen($accentColor, [Math]::Max(1.0, $borderWidth * 0.8))
    $topLineY = $rectY + 1
    $g.DrawLine($accentPen, ($rectX + $cornerRadius), $topLineY, ($rectX + $rectW - $cornerRadius), $topLineY)
    $accentPen.Dispose()

    # 6. Draw border
    $borderPen = New-Object System.Drawing.Pen($borderColor, $borderWidth)
    $g.DrawPath($borderPen, $cardPath)
    $borderPen.Dispose()

    $cardPath.Dispose()
    $g.Dispose()

    # Save
    $bmp.Save($filePath, [System.Drawing.Imaging.ImageFormat]::Png)
    $bmp.Dispose()

    Write-Host "  Saved: $filePath"
}

Write-Host ""
Write-Host "All 6 dark encadres created successfully!"
