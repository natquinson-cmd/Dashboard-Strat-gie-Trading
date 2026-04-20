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

# Colors - same as buttons but thinner
$cardColor = [System.Drawing.Color]::FromArgb(255, 15, 23, 42)
$borderIndigo = [System.Drawing.Color]::FromArgb(180, 99, 102, 241)    # slightly less opaque
$glowSubtle = [System.Drawing.Color]::FromArgb(35, 99, 102, 241)      # subtle outer glow only
$shadowColor = [System.Drawing.Color]::FromArgb(80, 0, 0, 0)

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
    [int]$margin = [Math]::Max(10, [int]($minDim * 0.04))
    [int]$shadowOff = [Math]::Max(2, [int]($minDim * 0.01))
    [int]$cornerRad = [Math]::Max(14, [int]($minDim * 0.065))

    [int]$rx = $margin; [int]$ry = $margin
    [int]$rw = $w - 2 * $margin; [int]$rh = $h - 2 * $margin

    # 1. Shadow (subtle)
    $sb = New-Object System.Drawing.SolidBrush($shadowColor)
    $sp = New-RoundedRectPath ([int]($rx+$shadowOff)) ([int]($ry+$shadowOff)) $rw $rh $cornerRad
    $g.FillPath($sb, $sp); $sp.Dispose(); $sb.Dispose()

    # 2. Single subtle glow layer (just 2px expansion)
    $gb = New-Object System.Drawing.SolidBrush($glowSubtle)
    $gp = New-RoundedRectPath ([int]($rx-2)) ([int]($ry-2)) ([int]($rw+4)) ([int]($rh+4)) ([int]($cornerRad+2))
    $g.FillPath($gb, $gp); $gp.Dispose(); $gb.Dispose()

    # 3. Card body
    $cb = New-Object System.Drawing.SolidBrush($cardColor)
    $cp = New-RoundedRectPath $rx $ry $rw $rh $cornerRad
    $g.FillPath($cb, $cp); $cb.Dispose()

    # 4. Thin indigo border (1.5px like the buttons)
    $bp = New-Object System.Drawing.Pen($borderIndigo, 1.5)
    $g.DrawPath($bp, $cp); $bp.Dispose()

    $cp.Dispose(); $g.Dispose()

    $tempPath = Join-Path $imageFolder "temp_enc.png"
    $bmp.Save($tempPath, [System.Drawing.Imaging.ImageFormat]::Png)
    $bmp.Dispose()
    Copy-Item $tempPath $filePath -Force
    Remove-Item $tempPath
    Write-Host "  OK"
}
Write-Host "Done!"
