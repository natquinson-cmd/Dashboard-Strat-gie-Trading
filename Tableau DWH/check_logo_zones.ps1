Add-Type -AssemblyName System.IO.Compression.FileSystem

$twbxPath = 'C:\Users\quinson\Desktop\Claude\Dasboard suivi projet DataWarehouse.twbx'
$tempDir = 'C:\Users\quinson\Desktop\Claude\Tableau DWH\twbx_check2'
if (Test-Path $tempDir) { Remove-Item $tempDir -Recurse -Force }
[System.IO.Compression.ZipFile]::ExtractToDirectory($twbxPath, $tempDir)

$twbFile = Get-ChildItem -Path $tempDir -Filter "*.twb" | Select-Object -First 1
$content = Get-Content $twbFile.FullName -Raw

# Find all lines around Logo EPFL
$lines = $content -split "`n"
for ($i = 0; $i -lt $lines.Count; $i++) {
    if ($lines[$i] -match 'Logo EPFL') {
        $start = [Math]::Max(0, $i - 1)
        $end = [Math]::Min($lines.Count - 1, $i + 10)
        Write-Host "=== Line $($i+1) ==="
        for ($j = $start; $j -le $end; $j++) {
            Write-Host "$($j+1): $($lines[$j])"
        }
        Write-Host ""
    }
}

Remove-Item $tempDir -Recurse -Force
