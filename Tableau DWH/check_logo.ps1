Add-Type -AssemblyName System.Drawing
$img = [System.Drawing.Image]::FromFile('C:\Users\quinson\Desktop\Claude\Tableau DWH\twbx_extracted\Image\Logo EPFL.png')
Write-Host "Logo EPFL.png: $($img.Width)x$($img.Height), PixelFormat=$($img.PixelFormat)"
$img.Dispose()
$img2 = [System.Drawing.Image]::FromFile('C:\Users\quinson\Desktop\Claude\Tableau DWH\twbx_extracted\Image\Logo EPFL - ORIGINAL.png')
Write-Host "Logo EPFL - ORIGINAL.png: $($img2.Width)x$($img2.Height), PixelFormat=$($img2.PixelFormat)"
$img2.Dispose()
