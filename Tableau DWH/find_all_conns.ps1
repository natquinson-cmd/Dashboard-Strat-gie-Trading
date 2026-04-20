Add-Type -AssemblyName System.IO.Compression.FileSystem
$twbxPath = 'C:\Users\quinson\Desktop\Claude\Dasboard suivi projet DataWarehouse.twbx'
$tempDir = 'C:\Users\quinson\Desktop\Claude\Tableau DWH\twbx_conn'
if (Test-Path $tempDir) { Remove-Item $tempDir -Recurse -Force }
[System.IO.Compression.ZipFile]::ExtractToDirectory($twbxPath, $tempDir)
$twbFile = (Get-ChildItem -Path $tempDir -Filter "*.twb" | Select-Object -First 1).FullName
$lines = [System.IO.File]::ReadAllLines($twbFile, [System.Text.Encoding]::UTF8)

Write-Host "=== ALL <connection ... /> blocks ==="
for ($i = 0; $i -lt $lines.Count; $i++) {
    if ($lines[$i] -match "<connection ") {
        Write-Host "$($i+1): $($lines[$i].TrimEnd())"
    }
}
Write-Host "`n=== datasource name/caption ==="
for ($i = 0; $i -lt $lines.Count; $i++) {
    if ($lines[$i] -match "<datasource " -and $lines[$i] -notmatch "dependencies") {
        Write-Host "$($i+1): $($lines[$i].TrimEnd())"
    }
}
Write-Host "`n=== is there a local Excel connection? ==="
for ($i = 0; $i -lt $lines.Count; $i++) {
    if ($lines[$i] -match "class='excel|excel-direct|\.xlsx") {
        Write-Host "$($i+1): $($lines[$i].TrimEnd())"
    }
}

# List packaged files
Write-Host "`n=== FILES IN TWBX ==="
Get-ChildItem $tempDir -Recurse | Where-Object { !$_.PSIsContainer } | ForEach-Object { Write-Host "$($_.FullName.Replace($tempDir,''))" }

Remove-Item $tempDir -Recurse -Force
