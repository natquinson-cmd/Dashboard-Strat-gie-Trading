Add-Type -AssemblyName System.Drawing

$imgPath = "C:\Users\quinson\Desktop\Claude\Tableau DWH\KPI_Box_Shadow_original.png"
$bmp = [System.Drawing.Bitmap]::new($imgPath)

Write-Host "=== KPI Box Shadow Shape (300x300) ==="

# Vertical scan at center
$cx = 150
Write-Host "`n--- Vertical scan at x=$cx ---"
for ($y = 0; $y -lt 300; $y += 10) {
    $p = $bmp.GetPixel($cx, $y)
    Write-Host "  y=$y : R=$($p.R) G=$($p.G) B=$($p.B) A=$($p.A)"
}

# Horizontal scan at center
$cy = 150
Write-Host "`n--- Horizontal scan at y=$cy ---"
for ($x = 0; $x -lt 300; $x += 10) {
    $p = $bmp.GetPixel($x, $cy)
    Write-Host "  x=$x : R=$($p.R) G=$($p.G) B=$($p.B) A=$($p.A)"
}

# Check key corners and edges
Write-Host "`n--- Key points ---"
$points = @(
    @(0,0), @(10,10), @(20,20), @(30,30),
    @(150,0), @(150,10), @(150,20), @(150,30),
    @(150,270), @(150,280), @(150,290), @(150,299),
    @(0,150), @(10,150), @(20,150), @(30,150),
    @(270,150), @(280,150), @(290,150), @(299,150)
)
foreach ($pt in $points) {
    $p = $bmp.GetPixel($pt[0], $pt[1])
    Write-Host "  ($($pt[0]),$($pt[1])) : R=$($p.R) G=$($p.G) B=$($p.B) A=$($p.A)"
}

$bmp.Dispose()
