Add-Type -AssemblyName System.IO.Compression.FileSystem

$twbxPath = 'C:\Users\quinson\Desktop\Claude\Dasboard suivi projet DataWarehouse.twbx'
$tempDir = 'C:\Users\quinson\Desktop\Claude\Tableau DWH\twbx_inspect2'
if (Test-Path $tempDir) { Remove-Item $tempDir -Recurse -Force }
[System.IO.Compression.ZipFile]::ExtractToDirectory($twbxPath, $tempDir)

$twbFile = (Get-ChildItem -Path $tempDir -Filter "*.twb" | Select-Object -First 1).FullName
$lines = [System.IO.File]::ReadAllLines($twbFile, [System.Text.Encoding]::UTF8)

# Find empty zones near Suivi Retard
Write-Host "=== EMPTY ZONES NEAR SUIVI RETARD (13600-13800) ==="
for ($i = 13600; $i -lt 13800; $i++) {
    if ($lines[$i] -match "type-v2='empty'") {
        $end = [Math]::Min($lines.Count - 1, $i + 8)
        for ($j = $i; $j -le $end; $j++) {
            Write-Host "$($j+1): $($lines[$j].TrimEnd())"
        }
        Write-Host ""
    }
}

# Also check Suivi Global
Write-Host "=== EMPTY ZONES NEAR SUIVI GLOBAL (13900-14200) ==="
for ($i = 13900; $i -lt 14200; $i++) {
    if ($lines[$i] -match "type-v2='empty'") {
        $end = [Math]::Min($lines.Count - 1, $i + 8)
        for ($j = $i; $j -le $end; $j++) {
            Write-Host "$($j+1): $($lines[$j].TrimEnd())"
        }
        Write-Host ""
    }
}

Remove-Item $tempDir -Recurse -Force
