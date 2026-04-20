Add-Type -AssemblyName System.IO.Compression.FileSystem
Add-Type -AssemblyName System.Drawing

$twbxPath = 'C:\Users\quinson\Desktop\Claude\Dasboard suivi projet DataWarehouse.twbx'
$tempDir = 'C:\Users\quinson\Desktop\Claude\Tableau DWH\twbx_help'
if (Test-Path $tempDir) { Remove-Item $tempDir -Recurse -Force }
[System.IO.Compression.ZipFile]::ExtractToDirectory($twbxPath, $tempDir)

# List all images
Write-Host "=== ALL IMAGES ==="
Get-ChildItem "$tempDir\Image" | ForEach-Object {
    $img = [System.Drawing.Image]::FromFile($_.FullName)
    Write-Host "$($_.Name): $($img.Width)x$($img.Height)"
    $img.Dispose()
}

# Search for glossaire/help zones in TWB
$twbFile = (Get-ChildItem -Path $tempDir -Filter "*.twb" | Select-Object -First 1).FullName
$lines = [System.IO.File]::ReadAllLines($twbFile, [System.Text.Encoding]::UTF8)

Write-Host "`n=== GLOSSAIRE / HELP ZONES ==="
for ($i = 0; $i -lt $lines.Count; $i++) {
    if ($lines[$i] -match "Glossaire|glossaire|aide|help|\?") {
        Write-Host "$($i+1): $($lines[$i].TrimEnd())"
    }
}

Write-Host "`nExtracted to: $tempDir"
