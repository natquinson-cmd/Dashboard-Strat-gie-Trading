Add-Type -AssemblyName System.IO.Compression.FileSystem
$twbxPath = 'C:\Users\quinson\Desktop\Claude\Dasboard suivi projet DataWarehouse.twbx'
$tempDir = 'C:\Users\quinson\Desktop\Claude\Tableau DWH\twbx_pivot2'
if (Test-Path $tempDir) { Remove-Item $tempDir -Recurse -Force }
[System.IO.Compression.ZipFile]::ExtractToDirectory($twbxPath, $tempDir)
$twbFile = (Get-ChildItem -Path $tempDir -Filter "*.twb" | Select-Object -First 1).FullName
$lines = [System.IO.File]::ReadAllLines($twbFile, [System.Text.Encoding]::UTF8)

# Search for relation with type='collection' or 'union' or pivot sources
Write-Host "=== RELATION BLOCKS CONTAINING PIVOT ==="
for ($i = 0; $i -lt $lines.Count; $i++) {
    if ($lines[$i] -match "relation |<relation|connection class|table='") {
        Write-Host "$($i+1): $($lines[$i].TrimEnd())"
    }
}
Write-Host "---"
# Find where Noms des champs is defined (the pivot field), look 20 lines before and after
for ($i = 0; $i -lt $lines.Count; $i++) {
    if ($lines[$i] -match "Noms des champs de tableau") {
        Write-Host "Found at line $($i+1)"
    }
}
Remove-Item $tempDir -Recurse -Force
