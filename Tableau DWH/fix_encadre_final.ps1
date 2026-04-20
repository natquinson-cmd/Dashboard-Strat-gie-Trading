[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

Add-Type -AssemblyName System.Drawing

$imageFolder = "C:\Users\quinson\Desktop\Claude\Tableau DWH\twbx_extracted\Image"
$twbPath = "C:\Users\quinson\Desktop\Claude\Tableau DWH\twbx_extracted\Dasboard DataWarehouse V4.twb"

# Read TWB as raw bytes to extract exact filenames
$twbContent = [System.IO.File]::ReadAllText($twbPath, [System.Text.Encoding]::UTF8)

# Extract all Encadre image references from TWB
$regex = [regex]"param='Image/(Encadr[^']+\.png)'"
$twbMatches = $regex.Matches($twbContent)

$expectedNames = @()
foreach ($m in $twbMatches) {
    $name = $m.Groups[1].Value
    if ($expectedNames -notcontains $name) {
        $expectedNames += $name
    }
}

Write-Host "=== Image names referenced in TWB ==="
foreach ($n in $expectedNames) {
    Write-Host "  '$n'"
    # Check hex bytes of the e-accent character
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($n)
    $hexStr = ($bytes | ForEach-Object { $_.ToString("X2") }) -join " "
    Write-Host "    Hex: $hexStr"
}

# Colors for dark encadres
$cardColor = [System.Drawing.Color]::FromArgb(255, 30, 41, 59)
$borderColor = [System.Drawing.Color]::FromArgb(220, 51, 65, 85)
$shadowColor = [System.Drawing.Color]::FromArgb(100, 0, 0, 0)
$glowColor = [System.Drawing.Color]::FromArgb(50, 99, 102, 241)
$topAccentColor = [System.Drawing.Color]::FromArgb(80, 99, 102, 241)

# Dimension map (from original images)
$dimMap = @{
    "Haut Gauche" = @(534, 237)
    "Haut Milieu" = @(315, 225)
    "Haut Droite" = @(408, 377)
    "milieu Page" = @(1365, 226)
    "bas gauche" = @(1268, 319)
    "bas droite" = @(487, 323)
}

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

function Create-DarkEncadre {
    param([string]$filePath, [int]$w, [int]$h)

    $bmp = New-Object System.Drawing.Bitmap($w, $h, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::HighQuality
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

    # Shadow
    $sb = New-Object System.Drawing.SolidBrush($shadowColor)
    $sp = New-RoundedRectPath -x ([int]($rx + $shadowOff)) -y ([int]($ry + $shadowOff)) -width $rw -height $rh -radius $cornerRad
    $g.FillPath($sb, $sp); $sp.Dispose(); $sb.Dispose()

    # Glow
    $gb = New-Object System.Drawing.SolidBrush($glowColor)
    $gp = New-RoundedRectPath -x ([int]($rx - 2)) -y ([int]($ry - 2)) -width ([int]($rw + 4)) -height ([int]($rh + 4)) -radius ([int]($cornerRad + 2))
    $g.FillPath($gb, $gp); $gp.Dispose(); $gb.Dispose()

    # Card body
    $cb = New-Object System.Drawing.SolidBrush($cardColor)
    $cp = New-RoundedRectPath -x $rx -y $ry -width $rw -height $rh -radius $cornerRad
    $g.FillPath($cb, $cp); $cb.Dispose()

    # Top accent
    $ap = New-Object System.Drawing.Pen($topAccentColor, 2.0)
    $g.DrawLine($ap, ($rx + $cornerRad), ($ry + 2), ($rx + $rw - $cornerRad), ($ry + 2))
    $ap.Dispose()

    # Border
    $bp = New-Object System.Drawing.Pen($borderColor, $bw)
    $g.DrawPath($bp, $cp); $bp.Dispose()
    $cp.Dispose()
    $g.Dispose()

    # Save using .NET directly to control the exact filename
    $bmp.Save($filePath, [System.Drawing.Imaging.ImageFormat]::Png)
    $bmp.Dispose()
}

Write-Host ""
Write-Host "=== Creating dark encadres with exact TWB filenames ==="

foreach ($name in $expectedNames) {
    $targetPath = [System.IO.Path]::Combine($imageFolder, $name)

    # Find matching dimensions
    $w = 500; $h = 300  # defaults
    foreach ($key in $dimMap.Keys) {
        if ($name -match [regex]::Escape($key)) {
            $w = $dimMap[$key][0]
            $h = $dimMap[$key][1]
            break
        }
    }

    Write-Host "Creating: $name (${w}x${h})"
    Write-Host "  Path: $targetPath"

    Create-DarkEncadre -filePath $targetPath -w $w -h $h

    $exists = [System.IO.File]::Exists($targetPath)
    Write-Host "  File exists after save: $exists"
}

# Final verification
Write-Host ""
Write-Host "=== Final verification ==="
foreach ($name in $expectedNames) {
    $targetPath = [System.IO.Path]::Combine($imageFolder, $name)
    $exists = [System.IO.File]::Exists($targetPath)
    $status = if ($exists) { "FOUND" } else { "MISSING" }
    Write-Host "  [$status] $name"
}
