Add-Type -AssemblyName System.Drawing

$logoPath = "C:\Users\quinson\Desktop\Claude\Tableau DWH\twbx_extracted\Image\Logo EPFL.png"
$tempPath = "C:\Users\quinson\Desktop\Claude\Tableau DWH\twbx_extracted\Image\Logo EPFL_temp.png"

# Load and convert to 32-bit ARGB (handles indexed pixel formats)
$orig = [System.Drawing.Image]::FromFile($logoPath)
$w = $orig.Width
$h = $orig.Height
Write-Host "Logo size: ${w}x${h}, Format: $($orig.PixelFormat)"

$bmp = New-Object System.Drawing.Bitmap($w, $h, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.DrawImage($orig, 0, 0, $w, $h)
$g.Dispose()
$orig.Dispose()

Write-Host "Converted to 32-bit ARGB"

# Replace white/near-white pixels with transparent
$threshold = 235
$pixelsChanged = 0

for ($y = 0; $y -lt $h; $y++) {
    for ($x = 0; $x -lt $w; $x++) {
        $pixel = $bmp.GetPixel($x, $y)
        if ($pixel.R -ge $threshold -and $pixel.G -ge $threshold -and $pixel.B -ge $threshold) {
            $bmp.SetPixel($x, $y, [System.Drawing.Color]::FromArgb(0, 0, 0, 0))
            $pixelsChanged++
        }
    }
}

Write-Host "Pixels made transparent: $pixelsChanged / $($w * $h)"

# Save to temp file then replace
$bmp.Save($tempPath, [System.Drawing.Imaging.ImageFormat]::Png)
$bmp.Dispose()

# Backup original
$backupPath = "C:\Users\quinson\Desktop\Claude\Tableau DWH\twbx_extracted\Image\Logo EPFL - ORIGINAL.png"
if (-not (Test-Path $backupPath)) {
    Copy-Item $logoPath $backupPath
    Write-Host "Backup saved: $backupPath"
}

# Replace original with transparent version
Copy-Item $tempPath $logoPath -Force
Remove-Item $tempPath
Write-Host "Done! Transparent logo saved: $logoPath"
