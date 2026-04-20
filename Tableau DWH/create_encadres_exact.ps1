Add-Type -AssemblyName System.Drawing

$imageFolder = "C:\Users\quinson\Desktop\Claude\Tableau DWH\twbx_extracted\Image"

# Exact filenames as in the TWB (UTF-8 with proper e-acute U+00E9)
$fileSpecs = @(
    @{ Name = "Encadr$(([char]0x00E9)) Haut Gauche Page1.png"; W = 534; H = 237 },
    @{ Name = "Encadr$(([char]0x00E9)) Haut Milieu Page1.png"; W = 315; H = 225 },
    @{ Name = "Encadr$(([char]0x00E9)) Haut Droite Page1.png"; W = 408; H = 377 },
    @{ Name = "Encadr$(([char]0x00E9)) milieu Page 1.png"; W = 1365; H = 226 },
    @{ Name = "Encadr$(([char]0x00E9)) bas gauche Page1.png"; W = 1268; H = 319 },
    @{ Name = "Encadr$(([char]0x00E9)) bas droite Page1.png"; W = 487; H = 323 }
)

# Colors
$cardColor = [System.Drawing.Color]::FromArgb(255, 30, 41, 59)
$borderColor = [System.Drawing.Color]::FromArgb(220, 51, 65, 85)
$shadowColor = [System.Drawing.Color]::FromArgb(100, 0, 0, 0)
$glowColor = [System.Drawing.Color]::FromArgb(50, 99, 102, 241)
$topAccentColor = [System.Drawing.Color]::FromArgb(80, 99, 102, 241)

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
    $filePath = [System.IO.Path]::Combine($imageFolder, $name)

    Write-Host "Creating: $name (${w}x${h})"

    $bmp = New-Object System.Drawing.Bitmap($w, $h, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::HighQuality
    $g.Clear([System.Drawing.Color]::Transparent)

    $minDim = [Math]::Min($w, $h)
    [int]$margin = [Math]::Max(10, [int]($minDim * 0.04))
    [int]$shadowOff = [Math]::Max(4, [int]($minDim * 0.02))
    [int]$cornerRad = [Math]::Max(14, [int]($minDim * 0.06))
    $bw = [Math]::Max(1.5, [Math]::Min(2.5, $w * 0.004))
    [int]$rx = $margin; [int]$ry = $margin
    [int]$rw = $w - 2 * $margin; [int]$rh = $h - 2 * $margin

    # Shadow
    $sb = New-Object System.Drawing.SolidBrush($shadowColor)
    $sp = New-RoundedRectPath ([int]($rx+$shadowOff)) ([int]($ry+$shadowOff)) $rw $rh $cornerRad
    $g.FillPath($sb, $sp); $sp.Dispose(); $sb.Dispose()
    # Glow
    $gb = New-Object System.Drawing.SolidBrush($glowColor)
    $gp = New-RoundedRectPath ([int]($rx-2)) ([int]($ry-2)) ([int]($rw+4)) ([int]($rh+4)) ([int]($cornerRad+2))
    $g.FillPath($gb, $gp); $gp.Dispose(); $gb.Dispose()
    # Card
    $cb = New-Object System.Drawing.SolidBrush($cardColor)
    $cp = New-RoundedRectPath $rx $ry $rw $rh $cornerRad
    $g.FillPath($cb, $cp); $cb.Dispose()
    # Top accent
    $ap = New-Object System.Drawing.Pen($topAccentColor, 2.0)
    $g.DrawLine($ap, ($rx+$cornerRad), ($ry+2), ($rx+$rw-$cornerRad), ($ry+2))
    $ap.Dispose()
    # Border
    $bp = New-Object System.Drawing.Pen($borderColor, $bw)
    $g.DrawPath($bp, $cp); $bp.Dispose()
    $cp.Dispose(); $g.Dispose()

    $bmp.Save($filePath, [System.Drawing.Imaging.ImageFormat]::Png)
    $bmp.Dispose()

    $exists = [System.IO.File]::Exists($filePath)
    Write-Host "  Saved: $exists  Path: $filePath"
}

# Verify ALL files match TWB references
Write-Host ""
Write-Host "=== Verification: checking TWB references ==="
$twbPath = "C:\Users\quinson\Desktop\Claude\Tableau DWH\twbx_extracted\Dasboard DataWarehouse V4.twb"
$twbContent = [System.IO.File]::ReadAllText($twbPath, [System.Text.Encoding]::UTF8)

$expectedNames = @(
    "Encadr$([char]0xE9) Haut Droite Page1.png",
    "Encadr$([char]0xE9) Haut Milieu Page1.png",
    "Encadr$([char]0xE9) Haut Gauche Page1.png",
    "Encadr$([char]0xE9) bas droite Page1.png",
    "Encadr$([char]0xE9) bas gauche Page1.png",
    "Encadr$([char]0xE9) milieu Page 1.png"
)

foreach ($n in $expectedNames) {
    $fullRef = "Image/$n"
    $inTwb = $twbContent.Contains($fullRef)
    $onDisk = [System.IO.File]::Exists([System.IO.Path]::Combine($imageFolder, $n))
    Write-Host "  TWB=$inTwb  Disk=$onDisk  $n"
}

# List ALL files starting with Encadr in the folder
Write-Host ""
Write-Host "=== All Encadr* files on disk ==="
[System.IO.Directory]::GetFiles($imageFolder, "Encadr*") | ForEach-Object {
    $fi = [System.IO.FileInfo]::new($_)
    Write-Host "  $($fi.Name)  ($($fi.Length) bytes)"
}
