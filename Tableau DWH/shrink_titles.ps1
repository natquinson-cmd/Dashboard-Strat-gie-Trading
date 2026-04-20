Add-Type -AssemblyName System.IO.Compression.FileSystem

$twbxPath = 'C:\Users\quinson\Desktop\Claude\Dasboard suivi projet DataWarehouse.twbx'
$tempDir = 'C:\Users\quinson\Desktop\Claude\Tableau DWH\twbx_titles'
if (Test-Path $tempDir) { Remove-Item $tempDir -Recurse -Force }
[System.IO.Compression.ZipFile]::ExtractToDirectory($twbxPath, $tempDir)

$twbFile = (Get-ChildItem -Path $tempDir -Filter "*.twb" | Select-Object -First 1).FullName
$bytes = [System.IO.File]::ReadAllBytes($twbFile)
$utf8 = New-Object System.Text.UTF8Encoding($false)
$content = $utf8.GetString($bytes)

# Count before
$before = ([regex]::Matches($content, "fontname='Arial' fontsize='36'")).Count
Write-Host "Before: $before matches of fontsize='36' with fontname='Arial'"

# Replace title font size 36 -> 32 (Arial font, used for dashboard titles)
$content = $content.Replace("fontname='Arial' fontsize='36'", "fontname='Arial' fontsize='32'")

$after = ([regex]::Matches($content, "fontname='Arial' fontsize='32'")).Count
Write-Host "After: $after matches of fontsize='32'"

[System.IO.File]::WriteAllBytes($twbFile, $utf8.GetBytes($content))

try {
    $xml = New-Object System.Xml.XmlDocument
    $xml.Load($twbFile)
    Write-Host "XML: OK"
} catch {
    Write-Host "XML ERROR: $_"
}

$tempZip = "$tempDir.zip"
if (Test-Path $tempZip) { Remove-Item $tempZip -Force }
[System.IO.Compression.ZipFile]::CreateFromDirectory($tempDir, $tempZip)
Copy-Item $tempZip $twbxPath -Force
Remove-Item $tempZip -Force
Remove-Item $tempDir -Recurse -Force
Write-Host "TWBX repackaged"
