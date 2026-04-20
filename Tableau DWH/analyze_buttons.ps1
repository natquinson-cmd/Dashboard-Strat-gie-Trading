Add-Type -AssemblyName System.IO.Compression.FileSystem

$twbxPath = 'C:\Users\quinson\Desktop\Claude\Dasboard suivi projet DataWarehouse.twbx'
$tempDir = 'C:\Users\quinson\Desktop\Claude\Tableau DWH\twbx_analyze'
if (Test-Path $tempDir) { Remove-Item $tempDir -Recurse -Force }
[System.IO.Compression.ZipFile]::ExtractToDirectory($twbxPath, $tempDir)

$twbFile = (Get-ChildItem -Path $tempDir -Filter "*.twb" | Select-Object -First 1).FullName
$lines = [System.IO.File]::ReadAllLines($twbFile, [System.Text.Encoding]::UTF8)

# Find all button zones and nearby text/button elements
Write-Host "=== BUTTON BITMAP ZONES ==="
for ($i = 0; $i -lt $lines.Count; $i++) {
    if ($lines[$i] -match "Bouton (milieu|droit|gauche|seul)\.png") {
        Write-Host "$($i+1): $($lines[$i].TrimEnd())"
    }
}

Write-Host "`n=== NAVIGATION BUTTON TEXT ZONES (goto-sheet) ==="
for ($i = 0; $i -lt $lines.Count; $i++) {
    if ($lines[$i] -match "tabdoc:goto-sheet") {
        # Show the zone and caption
        $start = [Math]::Max(0, $i - 3)
        $end = [Math]::Min($lines.Count - 1, $i + 6)
        for ($j = $start; $j -le $end; $j++) {
            Write-Host "$($j+1): $($lines[$j].TrimEnd())"
        }
        Write-Host ""
    }
}

Remove-Item $tempDir -Recurse -Force
