Add-Type -AssemblyName System.IO.Compression.FileSystem
Add-Type -AssemblyName System.Drawing

$twbxPath = 'C:\Users\quinson\Desktop\Claude\Dasboard suivi projet DataWarehouse.twbx'
$tempDir = 'C:\Users\quinson\Desktop\Claude\Tableau DWH\twbx_encadres'
if (Test-Path $tempDir) { Remove-Item $tempDir -Recurse -Force }
[System.IO.Compression.ZipFile]::ExtractToDirectory($twbxPath, $tempDir)

# Check current encadre images
Write-Host "=== ENCADRE IMAGES ==="
Get-ChildItem "$tempDir\Image\Encadr*" | ForEach-Object {
    $img = [System.Drawing.Image]::FromFile($_.FullName)
    Write-Host "$($_.Name): $($img.Width)x$($img.Height), $($img.PixelFormat)"
    $img.Dispose()
}

# Find encadre zones in TWB (Suivi Global = first page)
$twbFile = (Get-ChildItem -Path $tempDir -Filter "*.twb" | Select-Object -First 1).FullName
$lines = [System.IO.File]::ReadAllLines($twbFile, [System.Text.Encoding]::UTF8)

Write-Host "`n=== ENCADRE ZONES (Page 1 / Suivi Global) ==="
for ($i = 13970; $i -lt 14500; $i++) {
    if ($lines[$i] -match "Encadr") {
        Write-Host "$($i+1): $($lines[$i].TrimEnd())"
    }
}

Write-Host "`nExtracted to: $tempDir"
