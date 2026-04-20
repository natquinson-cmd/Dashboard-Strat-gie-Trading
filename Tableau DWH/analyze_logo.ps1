Add-Type -AssemblyName System.IO.Compression.FileSystem
Add-Type -AssemblyName System.Drawing

# Extract fresh copy to check
$twbxPath = 'C:\Users\quinson\Desktop\Claude\Dasboard suivi projet DataWarehouse.twbx'
$tempDir = 'C:\Users\quinson\Desktop\Claude\Tableau DWH\twbx_check'
if (Test-Path $tempDir) { Remove-Item $tempDir -Recurse -Force }
[System.IO.Compression.ZipFile]::ExtractToDirectory($twbxPath, $tempDir)

$logoPath = "$tempDir\Image\Logo EPFL.png"
$img = New-Object System.Drawing.Bitmap($logoPath)
Write-Host "Size: $($img.Width)x$($img.Height), Format: $($img.PixelFormat)"

# Sample corners and center to check alpha
$points = @(
    @(0,0), @(10,10), @($img.Width-1,0), @(0,$img.Height-1),
    @($img.Width-1,$img.Height-1), @([int]($img.Width/2), 5)
)
foreach ($p in $points) {
    $px = $img.GetPixel($p[0], $p[1])
    Write-Host "Pixel($($p[0]),$($p[1])): R=$($px.R) G=$($px.G) B=$($px.B) A=$($px.A)"
}

# Count transparent vs opaque
$transparent = 0
$opaque = 0
$semiWhite = 0
for ($y = 0; $y -lt $img.Height; $y++) {
    for ($x = 0; $x -lt $img.Width; $x++) {
        $px = $img.GetPixel($x, $y)
        if ($px.A -eq 0) { $transparent++ }
        elseif ($px.R -gt 200 -and $px.G -gt 200 -and $px.B -gt 200) { $semiWhite++ }
        else { $opaque++ }
    }
}
Write-Host "Transparent pixels: $transparent"
Write-Host "Semi-white (R,G,B > 200, opaque): $semiWhite"
Write-Host "Other opaque pixels: $opaque"
Write-Host "Total: $($img.Width * $img.Height)"

$img.Dispose()
Remove-Item $tempDir -Recurse -Force
