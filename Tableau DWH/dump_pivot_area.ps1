Add-Type -AssemblyName System.IO.Compression.FileSystem
$twbxPath = 'C:\Users\quinson\Desktop\Claude\Dasboard suivi projet DataWarehouse.twbx'
$tempDir = 'C:\Users\quinson\Desktop\Claude\Tableau DWH\twbx_px'
if (Test-Path $tempDir) { Remove-Item $tempDir -Recurse -Force }
[System.IO.Compression.ZipFile]::ExtractToDirectory($twbxPath, $tempDir)
$twbFile = (Get-ChildItem -Path $tempDir -Filter "*.twb" | Select-Object -First 1).FullName
$lines = [System.IO.File]::ReadAllLines($twbFile, [System.Text.Encoding]::UTF8)

# Dump lines around each pivot-related area
Write-Host "=== Lines 2420-2560 (main datasource) ==="
for ($i = 2420; $i -lt 2560 -and $i -lt $lines.Count; $i++) {
    Write-Host "$($i+1): $($lines[$i].TrimEnd())"
}
Remove-Item $tempDir -Recurse -Force
