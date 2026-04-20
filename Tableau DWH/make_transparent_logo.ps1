Add-Type -AssemblyName System.Drawing

$srcPath = 'C:\Users\quinson\Desktop\Claude\Tableau DWH\twbx_extracted\Image\Logo EPFL.png'
$outPath = 'C:\Users\quinson\Desktop\Claude\Tableau DWH\twbx_extracted\Image\Logo EPFL.png'

$src = New-Object System.Drawing.Bitmap($srcPath)
$dst = New-Object System.Drawing.Bitmap($src.Width, $src.Height, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)

for ($y = 0; $y -lt $src.Height; $y++) {
    for ($x = 0; $x -lt $src.Width; $x++) {
        $pixel = $src.GetPixel($x, $y)
        # If pixel is white or near-white (R,G,B all > 240), make transparent
        if ($pixel.R -gt 240 -and $pixel.G -gt 240 -and $pixel.B -gt 240) {
            $dst.SetPixel($x, $y, [System.Drawing.Color]::FromArgb(0, 255, 255, 255))
        } else {
            $dst.SetPixel($x, $y, $pixel)
        }
    }
}

$src.Dispose()
$dst.Save($outPath, [System.Drawing.Imaging.ImageFormat]::Png)
$dst.Dispose()
Write-Host "Logo saved with transparent background: $outPath"
