Add-Type -AssemblyName System.IO.Compression.FileSystem
$twbxPath = 'C:\Users\quinson\Desktop\Claude\Dasboard suivi projet DataWarehouse.twbx'
$tempDir = 'C:\Users\quinson\Desktop\Claude\Tableau DWH\twbx_pivot'
if (Test-Path $tempDir) { Remove-Item $tempDir -Recurse -Force }
[System.IO.Compression.ZipFile]::ExtractToDirectory($twbxPath, $tempDir)
$twbFile = (Get-ChildItem -Path $tempDir -Filter "*.twb" | Select-Object -First 1).FullName
$bytes = [System.IO.File]::ReadAllBytes($twbFile)
$utf8 = New-Object System.Text.UTF8Encoding($false)
$content = $utf8.GetString($bytes)
$lines = $content -split "`n"

Write-Host "=== PIVOT RELATIONS / COLUMNS ==="
for ($i = 0; $i -lt $lines.Count; $i++) {
    if ($lines[$i] -match "pivot|Pivot|tableau crois|field-reshape|remap-column-types|unpivot") {
        Write-Host "$($i+1): $($lines[$i].TrimEnd())"
    }
}
