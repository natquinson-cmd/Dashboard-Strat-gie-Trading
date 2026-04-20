Add-Type -AssemblyName System.IO.Compression.FileSystem

$twbxPath = 'C:\Users\quinson\Desktop\Claude\Dasboard suivi projet DataWarehouse.twbx'
$tempDir = 'C:\Users\quinson\Desktop\Claude\Tableau DWH\twbx_checknames'
if (Test-Path $tempDir) { Remove-Item $tempDir -Recurse -Force }
[System.IO.Compression.ZipFile]::ExtractToDirectory($twbxPath, $tempDir)

Write-Host "=== FILES IN IMAGE FOLDER ==="
Get-ChildItem "$tempDir\Image" | ForEach-Object {
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($_.Name)
    $hex = ($bytes | ForEach-Object { '{0:X2}' -f $_ }) -join ' '
    Write-Host "$($_.Name) | Size: $($_.Length) | Hex: $hex"
}

# Check what the TWB references
$twbFile = (Get-ChildItem -Path $tempDir -Filter "*.twb" | Select-Object -First 1).FullName
$content = [System.IO.File]::ReadAllText($twbFile, [System.Text.Encoding]::UTF8)
$matches = [regex]::Matches($content, "param='Image/Encadr[^']*'")
Write-Host "`n=== TWB REFERENCES ==="
$matches | ForEach-Object { Write-Host $_.Value } | Select-Object -Unique

Remove-Item $tempDir -Recurse -Force
