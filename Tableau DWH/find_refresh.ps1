Add-Type -AssemblyName System.IO.Compression.FileSystem
$twbxPath = 'C:\Users\quinson\Desktop\Claude\Dasboard suivi projet DataWarehouse.twbx'
$tempDir = 'C:\Users\quinson\Desktop\Claude\Tableau DWH\twbx_refresh'
if (Test-Path $tempDir) { Remove-Item $tempDir -Recurse -Force }
[System.IO.Compression.ZipFile]::ExtractToDirectory($twbxPath, $tempDir)
$twbFile = (Get-ChildItem -Path $tempDir -Filter "*.twb" | Select-Object -First 1).FullName
$lines = [System.IO.File]::ReadAllLines($twbFile, [System.Text.Encoding]::UTF8)
for ($i = 0; $i -lt $lines.Count; $i++) {
    if ($lines[$i] -match "Dernier refresh") {
        Write-Host "$($i+1): $($lines[$i].TrimEnd())"
    }
}
Remove-Item $tempDir -Recurse -Force
