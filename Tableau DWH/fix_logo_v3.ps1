Add-Type -AssemblyName System.IO.Compression.FileSystem
Add-Type -AssemblyName System.Drawing

$twbxPath = 'C:\Users\quinson\Desktop\Claude\Dasboard suivi projet DataWarehouse.twbx'
$tempDir = 'C:\Users\quinson\Desktop\Claude\Tableau DWH\twbx_logo_fix3'

# Clean and extract
if (Test-Path $tempDir) { Remove-Item $tempDir -Recurse -Force }
[System.IO.Compression.ZipFile]::ExtractToDirectory($twbxPath, $tempDir)
Write-Host "Extracted"

# 1. Make logo transparent
$logoPath = "$tempDir\Image\Logo EPFL.png"
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
Write-Host "Logo made transparent"

# 2. Fix TWB - read as raw bytes to preserve encoding
$twbFile = (Get-ChildItem -Path $tempDir -Filter "*.twb" | Select-Object -First 1).FullName
$bytes = [System.IO.File]::ReadAllBytes($twbFile)
$utf8 = New-Object System.Text.UTF8Encoding($false)
$content = $utf8.GetString($bytes)

# Remove background-color #faf5f4 lines only
$content = $content -replace "            <format attr='background-color' value='#faf5f4' />`r?`n", ""

# Write back with same UTF-8 no BOM encoding
[System.IO.File]::WriteAllBytes($twbFile, $utf8.GetBytes($content))
Write-Host "TWB updated (encoding preserved)"

# Validate XML
try {
    $xml = New-Object System.Xml.XmlDocument
    $xml.Load($twbFile)
    Write-Host "XML: OK"
} catch {
    Write-Host "XML ERROR: $_"
}

# 3. Repackage
$tempZip = "$tempDir.zip"
if (Test-Path $tempZip) { Remove-Item $tempZip -Force }
[System.IO.Compression.ZipFile]::CreateFromDirectory($tempDir, $tempZip)
Copy-Item $tempZip $twbxPath -Force
Remove-Item $tempZip -Force
Remove-Item $tempDir -Recurse -Force

Write-Host "TWBX repackaged: $twbxPath"
