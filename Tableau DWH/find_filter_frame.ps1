Add-Type -AssemblyName System.IO.Compression.FileSystem

$twbxPath = 'C:\Users\quinson\Desktop\Claude\Dasboard suivi projet DataWarehouse.twbx'
$tempDir = 'C:\Users\quinson\Desktop\Claude\Tableau DWH\twbx_inspect'
if (Test-Path $tempDir) { Remove-Item $tempDir -Recurse -Force }
[System.IO.Compression.ZipFile]::ExtractToDirectory($twbxPath, $tempDir)

$twbFile = (Get-ChildItem -Path $tempDir -Filter "*.twb" | Select-Object -First 1).FullName
$lines = [System.IO.File]::ReadAllLines($twbFile, [System.Text.Encoding]::UTF8)

# Find "Suivi Evolution" dashboard section
Write-Host "=== SEARCHING FOR SUIVI EVOLUTION DASHBOARD ==="
for ($i = 0; $i -lt $lines.Count; $i++) {
    if ($lines[$i] -match "Suivi Evolution</run>") {
        Write-Host "Line $($i+1): $($lines[$i].Trim())"
    }
}

# Find gray/filter-related zones near the filter area
Write-Host "`n=== ZONES WITH BACKGROUND-COLOR (around line 13100-13200) ==="
for ($i = 13090; $i -lt 13220; $i++) {
    if ($lines[$i] -match 'background-color|empty|Intervenant|Filtre|Projet|border-color') {
        Write-Host "$($i+1): $($lines[$i].Trim())"
    }
}

# Find the empty zone that forms the gray frame
Write-Host "`n=== EMPTY ZONES IN SUIVI EVOLUTION (13090-13550) ==="
for ($i = 13090; $i -lt 13550; $i++) {
    if ($lines[$i] -match "type-v2='empty'") {
        $start = $i
        $end = [Math]::Min($lines.Count - 1, $i + 8)
        for ($j = $start; $j -le $end; $j++) {
            Write-Host "$($j+1): $($lines[$j].Trim())"
        }
        Write-Host ""
    }
}

# List all images to find navigation bar
Write-Host "`n=== ALL IMAGES IN PACKAGE ==="
Get-ChildItem -Path "$tempDir\Image" | ForEach-Object { Write-Host $_.Name }

Remove-Item $tempDir -Recurse -Force
