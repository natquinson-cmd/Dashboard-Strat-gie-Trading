Add-Type -AssemblyName System.IO.Compression.FileSystem

$twbxPath = 'C:\Users\quinson\Desktop\Claude\Dasboard suivi projet DataWarehouse.twbx'
$tempDir = 'C:\Users\quinson\Desktop\Claude\Tableau DWH\twbx_debug'
if (Test-Path $tempDir) { Remove-Item $tempDir -Recurse -Force }
[System.IO.Compression.ZipFile]::ExtractToDirectory($twbxPath, $tempDir)

$twbFile = (Get-ChildItem -Path $tempDir -Filter "*.twb" | Select-Object -First 1).FullName
$bytes = [System.IO.File]::ReadAllBytes($twbFile)
$utf8 = New-Object System.Text.UTF8Encoding($false)
$content = $utf8.GetString($bytes)

# Check if zones are still empty or bitmap
$lines = $content -split "`n"
for ($i = 0; $i -lt $lines.Count; $i++) {
    if ($lines[$i] -match "id='1102'") {
        Write-Host "Line $($i+1): $($lines[$i].TrimEnd())"
        # Show hex of line ending
        $rawBytes = [System.Text.Encoding]::UTF8.GetBytes($lines[$i])
        $lastBytes = $rawBytes[($rawBytes.Length - 4)..($rawBytes.Length - 1)]
        Write-Host "  Last bytes: $($lastBytes | ForEach-Object { '0x{0:X2}' -f $_ })"
    }
}

# Check if file uses CRLF or LF
$crlfCount = ([regex]::Matches($content, "`r`n")).Count
$lfOnly = ([regex]::Matches($content, "(?<!`r)`n")).Count
Write-Host "`nCRLF: $crlfCount, LF-only: $lfOnly"

# Check if the images exist in the package
Write-Host "`nImages in package:"
Get-ChildItem "$tempDir\Image\Cadre*" | ForEach-Object { Write-Host "  $($_.Name) ($($_.Length) bytes)" }

Remove-Item $tempDir -Recurse -Force
