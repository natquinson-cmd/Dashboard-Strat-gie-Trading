Add-Type -AssemblyName System.Drawing

$imageFolder = "C:\Users\quinson\Desktop\Claude\Tableau DWH\twbx_extracted\Image"

# Find actual original files (the ones Tableau references)
$allFiles = Get-ChildItem "$imageFolder\Encadr*Page1.png" | Where-Object { $_.Name -notmatch 'ORIGINAL' }
# Also get milieu file separately in case naming differs
$milieuFiles = Get-ChildItem "$imageFolder\Encadr*milieu*Page*1.png" | Where-Object { $_.Name -notmatch 'ORIGINAL' }
$allFiles = @($allFiles) + @($milieuFiles) | Sort-Object FullName -Unique

Write-Host "Found $($allFiles.Count) encadre files to update:"

# MORE VISIBLE colors - higher contrast
$cardColor = [System.Drawing.Color]::FromArgb(255, 30, 41, 59)        # #1e293b (Tailwind slate-800) - more visible
$borderColor = [System.Drawing.Color]::FromArgb(220, 51, 65, 85)      # #334155 (Tailwind slate-700) - brighter border
$shadowColor = [System.Drawing.Color]::FromArgb(100, 0, 0, 0)         # stronger shadow
$glowColor = [System.Drawing.Color]::FromArgb(50, 99, 102, 241)       # #6366f1 stronger indigo glow
$topAccentColor = [System.Drawing.Color]::FromArgb(80, 99, 102, 241)  # visible top accent line

function New-RoundedRectPath {
    param([int]$x, [int]$y, [int]$width, [int]$height, [int]$radius)
    $path = New-Object System.Drawing.Drawing2D.GraphicsPath
    $d = $radius * 2
    if ($d -gt $width) { $d = $width; $radius = [int]($d / 2) }
    if ($d -gt $height) { $d = $height; $radius = [int]($d / 2) }
    $path.AddArc($x, $y, $d, $d, 180, 90)
    $path.AddArc($x + $width - $d, $y, $d, $d, 270, 90)
    $path.AddArc($x + $width - $d, $y + $height - $d, $d, $d, 0, 90)
    $path.AddArc($x, $y + $height - $d, $d, $d, 90, 90)
    $path.CloseFigure()
    return $path
}

foreach ($file in $allFiles) {
    $origPath = $file.FullName

    # Get dimensions
    $orig = [System.Drawing.Image]::FromFile($origPath)
    $w = $orig.Width
    $h = $orig.Height
    $orig.Dispose()

    Write-Host "Processing: $($file.Name) (${w}x${h})"

    $bmp = New-Object System.Drawing.Bitmap($w, $h, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::HighQuality
    $g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
    $g.Clear([System.Drawing.Color]::Transparent)

    $minDim = [Math]::Min($w, $h)
    [int]$margin = [Math]::Max(10, [int]($minDim * 0.04))
    [int]$shadowOff = [Math]::Max(4, [int]($minDim * 0.02))
    [int]$cornerRad = [Math]::Max(14, [int]($minDim * 0.06))
    $bw = [Math]::Max(1.5, [Math]::Min(2.5, $w * 0.004))

    [int]$rx = $margin
    [int]$ry = $margin
    [int]$rw = $w - 2 * $margin
    [int]$rh = $h - 2 * $margin

    # 1. Shadow (stronger, offset bottom-right)
    $shadowBrush = New-Object System.Drawing.SolidBrush($shadowColor)
    $shadowPath = New-RoundedRectPath -x ([int]($rx + $shadowOff)) -y ([int]($ry + $shadowOff)) -width $rw -height $rh -radius $cornerRad
    $g.FillPath($shadowBrush, $shadowPath)
    $shadowPath.Dispose()
    $shadowBrush.Dispose()

    # 2. Outer glow (more visible indigo)
    $glowBrush = New-Object System.Drawing.SolidBrush($glowColor)
    $glowPath = New-RoundedRectPath -x ([int]($rx - 2)) -y ([int]($ry - 2)) -width ([int]($rw + 4)) -height ([int]($rh + 4)) -radius ([int]($cornerRad + 2))
    $g.FillPath($glowBrush, $glowPath)
    $glowPath.Dispose()
    $glowBrush.Dispose()

    # 3. Main card body
    $cardBrush = New-Object System.Drawing.SolidBrush($cardColor)
    $cardPath = New-RoundedRectPath -x $rx -y $ry -width $rw -height $rh -radius $cornerRad
    $g.FillPath($cardBrush, $cardPath)
    $cardBrush.Dispose()

    # 4. Top accent line (visible indigo)
    $accentPen = New-Object System.Drawing.Pen($topAccentColor, 2.0)
    [int]$lineStartX = $rx + $cornerRad
    [int]$lineEndX = $rx + $rw - $cornerRad
    [int]$lineY = $ry + 2
    $g.DrawLine($accentPen, $lineStartX, $lineY, $lineEndX, $lineY)
    $accentPen.Dispose()

    # 5. Border (more visible)
    $borderPen = New-Object System.Drawing.Pen($borderColor, $bw)
    $g.DrawPath($borderPen, $cardPath)
    $borderPen.Dispose()

    $cardPath.Dispose()
    $g.Dispose()

    # Save via temp file
    $tempPath = Join-Path $imageFolder "temp_encadre.png"
    $bmp.Save($tempPath, [System.Drawing.Imaging.ImageFormat]::Png)
    $bmp.Dispose()

    Copy-Item $tempPath $origPath -Force
    Remove-Item $tempPath
    Write-Host "  Saved OK"
}

Write-Host ""
Write-Host "All 6 dark encadres updated with higher contrast!"
