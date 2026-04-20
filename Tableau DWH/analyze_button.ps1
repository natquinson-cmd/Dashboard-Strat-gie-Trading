Add-Type -AssemblyName System.Drawing
$imgPath = "C:\Users\quinson\Desktop\Claude\Tableau DWH\twbx_extracted\Image"
$bmp = [System.Drawing.Bitmap]::new("$imgPath\Bouton gauche.png")

Write-Host "=== Bouton gauche.png ($($bmp.Width) x $($bmp.Height)) ==="
Write-Host ""

# Sample pixels along vertical center column
$cx = [int]($bmp.Width / 2)
Write-Host "--- Vertical scan at x=$cx ---"
for ($y = 0; $y -lt $bmp.Height; $y += 3) {
    $p = $bmp.GetPixel($cx, $y)
    Write-Host "  y=$y : R=$($p.R) G=$($p.G) B=$($p.B) A=$($p.A)"
}

Write-Host ""
# Sample pixels along horizontal center row
$cy = [int]($bmp.Height / 2)
Write-Host "--- Horizontal scan at y=$cy ---"
for ($x = 0; $x -lt $bmp.Width; $x += 30) {
    $p = $bmp.GetPixel($x, $cy)
    Write-Host "  x=$x : R=$($p.R) G=$($p.G) B=$($p.B) A=$($p.A)"
}

Write-Host ""
# Check corners for rounding
Write-Host "--- Corners ---"
foreach ($pos in @(@(0,0), @(10,10), @(5,5), @($bmp.Width-1,0), @($bmp.Width-11,10), @(0,$bmp.Height-1), @(10,$bmp.Height-11))) {
    $p = $bmp.GetPixel($pos[0], $pos[1])
    Write-Host "  ($($pos[0]),$($pos[1])) : R=$($p.R) G=$($p.G) B=$($p.B) A=$($p.A)"
}

# Check for glossy gradient at top
Write-Host ""
Write-Host "--- Top gradient check (x=$cx, y=0..40) ---"
for ($y = 0; $y -lt 40; $y += 2) {
    $p = $bmp.GetPixel($cx, $y)
    Write-Host "  y=$y : R=$($p.R) G=$($p.G) B=$($p.B) A=$($p.A)"
}

$bmp.Dispose()
