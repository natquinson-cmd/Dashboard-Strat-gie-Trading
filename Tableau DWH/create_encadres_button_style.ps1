Add-Type -AssemblyName System.Drawing

$imageFolder = "C:\Users\quinson\Desktop\Claude\Tableau DWH\twbx_extracted\Image"

$fileSpecs = @(
    @{ Name = "Encadre Haut Gauche Page1.png"; W = 534; H = 237 },
    @{ Name = "Encadre Haut Milieu Page1.png"; W = 315; H = 225 },
    @{ Name = "Encadre Haut Droite Page1.png"; W = 408; H = 377 },
    @{ Name = "Encadre milieu Page 1.png"; W = 1365; H = 226 },
    @{ Name = "Encadre bas gauche Page1.png"; W = 1268; H = 319 },
    @{ Name = "Encadre bas droite Page1.png"; W = 487; H = 323 }
)

# Colors matching the button style
$cardColor = [System.Drawing.Color]::FromArgb(255, 15, 23, 42)        # #0f172a - very dark navy
$borderIndigo = [System.Drawing.Color]::FromArgb(200, 99, 102, 241)   # #6366f1 - bright indigo border
$glowOuter = [System.Drawing.Color]::FromArgb(60, 99, 102, 241)       # outer glow
$glowMid = [System.Drawing.Color]::FromArgb(100, 99, 102, 241)        # mid glow
$shadowColor = [System.Drawing.Color]::FromArgb(120, 0, 0, 0)         # shadow
$innerHighlight = [System.Drawing.Color]::FromArgb(20, 150, 160, 255) # subtle inner top highlight

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

foreach ($spec in $fileSpecs) {
    $name = $spec.Name
    $w = $spec.W
    $h = $spec.H
    $filePath = Join-Path $imageFolder $name

    Write-Host "Creating: $name (${w}x${h})"

    $bmp = New-Object System.Drawing.Bitmap($w, $h, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::HighQuality
    $g.Clear([System.Drawing.Color]::Transparent)

    $minDim = [Math]::Min($w, $h)
    [int]$margin = [Math]::Max(12, [int]($minDim * 0.05))
    [int]$shadowOff = [Math]::Max(3, [int]($minDim * 0.015))
    [int]$cornerRad = [Math]::Max(16, [int]($minDim * 0.07))

    [int]$rx = $margin
    [int]$ry = $margin
    [int]$rw = $w - 2 * $margin
    [int]$rh = $h - 2 * $margin

    # 1. Drop shadow
    $sb = New-Object System.Drawing.SolidBrush($shadowColor)
    $sp = New-RoundedRectPath ([int]($rx + $shadowOff)) ([int]($ry + $shadowOff)) $rw $rh $cornerRad
    $g.FillPath($sb, $sp); $sp.Dispose(); $sb.Dispose()

    # 2. Outer glow (large, diffuse indigo)
    $gb1 = New-Object System.Drawing.SolidBrush($glowOuter)
    $gp1 = New-RoundedRectPath ([int]($rx - 4)) ([int]($ry - 4)) ([int]($rw + 8)) ([int]($rh + 8)) ([int]($cornerRad + 4))
    $g.FillPath($gb1, $gp1); $gp1.Dispose(); $gb1.Dispose()

    # 3. Mid glow (tighter, brighter indigo)
    $gb2 = New-Object System.Drawing.SolidBrush($glowMid)
    $gp2 = New-RoundedRectPath ([int]($rx - 2)) ([int]($ry - 2)) ([int]($rw + 4)) ([int]($rh + 4)) ([int]($cornerRad + 2))
    $g.FillPath($gb2, $gp2); $gp2.Dispose(); $gb2.Dispose()

    # 4. Main card body
    $cb = New-Object System.Drawing.SolidBrush($cardColor)
    $cp = New-RoundedRectPath $rx $ry $rw $rh $cornerRad
    $g.FillPath($cb, $cp); $cb.Dispose()

    # 5. Inner subtle highlight at top (simulate 3D depth)
    $ihBrush = New-Object System.Drawing.SolidBrush($innerHighlight)
    [int]$highlightH = [Math]::Max(3, [int]($rh * 0.08))
    $ihPath = New-RoundedRectPath $rx $ry $rw $highlightH $cornerRad
    $g.FillPath($ihBrush, $ihPath); $ihPath.Dispose(); $ihBrush.Dispose()

    # 6. Bright indigo border (main visual element - like the buttons)
    $borderWidth = [Math]::Max(2.0, [Math]::Min(3.0, $minDim * 0.012))
    $bp = New-Object System.Drawing.Pen($borderIndigo, $borderWidth)
    $g.DrawPath($bp, $cp); $bp.Dispose()

    $cp.Dispose()
    $g.Dispose()

    # Save
    $tempPath = Join-Path $imageFolder "temp_enc.png"
    $bmp.Save($tempPath, [System.Drawing.Imaging.ImageFormat]::Png)
    $bmp.Dispose()
    Copy-Item $tempPath $filePath -Force
    Remove-Item $tempPath

    Write-Host "  OK"
}

Write-Host ""
Write-Host "All 6 encadres created with button style!"
