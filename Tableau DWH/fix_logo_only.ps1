Add-Type -AssemblyName System.IO.Compression.FileSystem
Add-Type -AssemblyName System.Drawing

$twbxPath = 'C:\Users\quinson\Desktop\Claude\Dasboard suivi projet DataWarehouse.twbx'
$tempDir = 'C:\Users\quinson\Desktop\Claude\Tableau DWH\twbx_logo_fix'

# Clean and extract
if (Test-Path $tempDir) { Remove-Item $tempDir -Recurse -Force }
[System.IO.Compression.ZipFile]::ExtractToDirectory($twbxPath, $tempDir)
Write-Host "Extracted TWBX"

# Find the logo file
$logoFiles = Get-ChildItem -Path $tempDir -Recurse -Filter "*Logo EPFL*"
foreach ($f in $logoFiles) {
    Write-Host "Found: $($f.FullName) ($($f.Length) bytes)"
}

# Make the logo transparent
$logoPath = $logoFiles[0].FullName
$src = New-Object System.Drawing.Bitmap($logoPath)
$dst = New-Object System.Drawing.Bitmap($src.Width, $src.Height, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)

for ($y = 0; $y -lt $src.Height; $y++) {
    for ($x = 0; $x -lt $src.Width; $x++) {
        $pixel = $src.GetPixel($x, $y)
        if ($pixel.R -gt 240 -and $pixel.G -gt 240 -and $pixel.B -gt 240) {
            $dst.SetPixel($x, $y, [System.Drawing.Color]::FromArgb(0, 255, 255, 255))
        } else {
            $dst.SetPixel($x, $y, $pixel)
        }
    }
}

$src.Dispose()
$dst.Save($logoPath, [System.Drawing.Imaging.ImageFormat]::Png)
$dst.Dispose()
Write-Host "Logo updated with transparent background"

# Repackage
$tempZip = 'C:\Users\quinson\Desktop\Claude\Tableau DWH\temp_logo_fix.zip'
if (Test-Path $tempZip) { Remove-Item $tempZip -Force }
[System.IO.Compression.ZipFile]::CreateFromDirectory($tempDir, $tempZip)
Copy-Item $tempZip $twbxPath -Force
Remove-Item $tempZip -Force
Remove-Item $tempDir -Recurse -Force

Write-Host "TWBX repackaged: $twbxPath"
Write-Host "Size: $([math]::Round((Get-Item $twbxPath).Length / 1MB, 2)) MB"
