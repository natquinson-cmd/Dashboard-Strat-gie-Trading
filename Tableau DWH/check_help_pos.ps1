Add-Type -AssemblyName System.IO.Compression.FileSystem

$twbxPath = 'C:\Users\quinson\Desktop\Claude\Dasboard suivi projet DataWarehouse.twbx'
$tempDir = 'C:\Users\quinson\Desktop\Claude\Tableau DWH\twbx_helppos'
if (Test-Path $tempDir) { Remove-Item $tempDir -Recurse -Force }
[System.IO.Compression.ZipFile]::ExtractToDirectory($twbxPath, $tempDir)

$twbFile = (Get-ChildItem -Path $tempDir -Filter "*.twb" | Select-Object -First 1).FullName
$lines = [System.IO.File]::ReadAllLines($twbFile, [System.Text.Encoding]::UTF8)

Write-Host "=== BUTTON + HELP ICON ZONES ==="
for ($i = 0; $i -lt $lines.Count; $i++) {
    if ($lines[$i] -match "(Bouton (milieu|droit|gauche)\.png|HelpIcon\.png|Glossaire).*type-v2='bitmap'" -or
        ($lines[$i] -match "Bouton (milieu|droit|gauche)\.png" -and $lines[$i] -notmatch "fixed-size")) {
        Write-Host "$($i+1): $($lines[$i].TrimEnd())"
    }
    if ($lines[$i] -match "HelpIcon" -and $lines[$i] -notmatch "fixed-size") {
        Write-Host "$($i+1): $($lines[$i].TrimEnd())"
    }
}

Remove-Item $tempDir -Recurse -Force
