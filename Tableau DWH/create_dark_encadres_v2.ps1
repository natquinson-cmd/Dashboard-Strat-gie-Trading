Add-Type -AssemblyName System.Drawing

$imageFolder = "C:\Users\quinson\Desktop\Claude\Tableau DWH\twbx_extracted\Image"

# Find actual files on disk using wildcard to resolve encoding
$allEncadres = Get-ChildItem "$imageFolder\Encadr*Page1.png" | Where-Object { $_.Length -gt 3000 }
# Also get the milieu file
$milieuFile = Get-ChildItem "$imageFolder\Encadr*milieu*Page*1.png" | Where-Object { $_.Length -gt 3000 }

# Combine and deduplicate
$allFiles = @()
$allFiles += $allEncadres
if ($milieuFile) { $allFiles += $milieuFile }
$allFiles = $allFiles | Sort-Object FullName -Unique

Write-Host "Found $($allFiles.Count) encadre files:"
foreach ($f in $allFiles) {
    Write-Host "  $($f.Name) ($($f.Length) bytes)"
}

# Also delete the wrongly-encoded duplicates
$badFiles = Get-ChildItem "$imageFolder\Encadr*" | Where-Object { $_.Length -lt 3000 -or $_.Name -match 'Ǹ' }
foreach ($bf in $badFiles) {
    Write-Host "Removing bad duplicate: $($bf.Name)"
    Remove-Item $bf.FullName -Force
}

# Colors
$cardColor = [System.Drawing.Color]::FromArgb(255, 17, 24, 39)        # #111827
$borderColor = [System.Drawing.Color]::FromArgb(180, 30, 42, 58)      # #1e2a3a
$shadowColor = [System.Drawing.Color]::FromArgb(60, 0, 0, 0)          # dark shadow
$glowColor = [System.Drawing.Color]::FromArgb(25, 99, 102, 241)       # #6366f1 subtle glow

# Helper function to create rounded rectangle path
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

    # Get original dimensions
    $orig = [System.Drawing.Image]::FromFile($origPath)
    $w = $orig.Width
    $h = $orig.Height
    $orig.Dispose()

    Write-Host ""
    Write-Host "Processing: $($file.Name) (${w}x${h})"

    # Backup original
    $backupDir = $imageFolder
    $backupName = $file.Name -replace '\.png$', ' - ORIGINAL.png'
    $backupPath = Join-Path $backupDir $backupName
    # Check if backup already exists by wildcard
    $existingBackup = Get-ChildItem "$imageFolder\*ORIGINAL*" | Where-Object { $_.Name -like "*$($file.BaseName.Substring(0,8))*ORIGINAL*" }
    if (-not $existingBackup) {
        Copy-Item $origPath $backupPath
        Write-Host "  Backup saved"
    }

    # Create new image
    $bmp = New-Object System.Drawing.Bitmap($w, $h, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::HighQuality
    $g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic

    # Transparent background
    $g.Clear([System.Drawing.Color]::Transparent)

    # Calculate proportional values
    $minDim = [Math]::Min($w, $h)
    $margin = [Math]::Max(8, [int]($minDim * 0.03))
    $shadowOff = [Math]::Max(3, [int]($minDim * 0.012))
    $cornerRad = [Math]::Max(12, [int]($minDim * 0.06))
    $bw = [Math]::Max(1.5, [Math]::Min(2.0, $w * 0.003))

    [int]$rx = $margin
    [int]$ry = $margin
    [int]$rw = $w - 2 * $margin
    [int]$rh = $h - 2 * $margin

    # 1. Shadow (offset bottom-right)
    $shadowBrush = New-Object System.Drawing.SolidBrush($shadowColor)
    $shadowPath = New-RoundedRectPath -x ([int]($rx + $shadowOff)) -y ([int]($ry + $shadowOff)) -width $rw -height $rh -radius $cornerRad
    $g.FillPath($shadowBrush, $shadowPath)
    $shadowPath.Dispose()
    $shadowBrush.Dispose()

    # 2. Subtle outer glow
    $glowBrush = New-Object System.Drawing.SolidBrush($glowColor)
    $glowPath = New-RoundedRectPath -x ([int]($rx - 1)) -y ([int]($ry - 1)) -width ([int]($rw + 2)) -height ([int]($rh + 2)) -radius ([int]($cornerRad + 1))
    $g.FillPath($glowBrush, $glowPath)
    $glowPath.Dispose()
    $glowBrush.Dispose()

    # 3. Main card body
    $cardBrush = New-Object System.Drawing.SolidBrush($cardColor)
    $cardPath = New-RoundedRectPath -x $rx -y $ry -width $rw -height $rh -radius $cornerRad
    $g.FillPath($cardBrush, $cardPath)
    $cardBrush.Dispose()

    # 4. Subtle top accent line (indigo)
    $accentColor = [System.Drawing.Color]::FromArgb(40, 99, 102, 241)
    $accentPen = New-Object System.Drawing.Pen($accentColor, 1.5)
    [int]$lineStartX = $rx + $cornerRad
    [int]$lineEndX = $rx + $rw - $cornerRad
    [int]$lineY = $ry + 1
    $g.DrawLine($accentPen, $lineStartX, $lineY, $lineEndX, $lineY)
    $accentPen.Dispose()

    # 5. Border
    $borderPen = New-Object System.Drawing.Pen($borderColor, $bw)
    $g.DrawPath($borderPen, $cardPath)
    $borderPen.Dispose()

    $cardPath.Dispose()
    $g.Dispose()

    # Save to temp then replace (avoid GDI+ lock issue)
    $tempPath = Join-Path $imageFolder "temp_encadre.png"
    $bmp.Save($tempPath, [System.Drawing.Imaging.ImageFormat]::Png)
    $bmp.Dispose()

    Copy-Item $tempPath $origPath -Force
    Remove-Item $tempPath
    Write-Host "  Saved: $origPath"
}

Write-Host ""
Write-Host "All dark encadres created successfully!"
