Add-Type -AssemblyName System.IO.Compression.FileSystem

$twbxPath = 'C:\Users\quinson\Desktop\Claude\Dasboard suivi projet DataWarehouse.twbx'
$tempDir = 'C:\Users\quinson\Desktop\Claude\Tableau DWH\twbx_helpcenter'
if (Test-Path $tempDir) { Remove-Item $tempDir -Recurse -Force }
[System.IO.Compression.ZipFile]::ExtractToDirectory($twbxPath, $tempDir)

$twbFile = (Get-ChildItem -Path $tempDir -Filter "*.twb" | Select-Object -First 1).FullName
$bytes = [System.IO.File]::ReadAllBytes($twbFile)
$utf8 = New-Object System.Text.UTF8Encoding($false)
$content = $utf8.GetString($bytes)

# Button centers:
# milieu/droit: y=2950, h=5000 -> center = 5450
# gauche:       y=2860, h=5000 -> center = 5360
#
# For circular icon: w=2222 -> 40px. For 40px height: h = 40/1100*100000 = 3636
# Icon on milieu/droit dashboards: center=5450, h=3636 -> y = 5450-1818 = 3632
# Icon on gauche dashboard: center=5360, h=3636 -> y = 5360-1818 = 3542
#
# HelpIcon zones (id 2088=Evo, 2089=Retard on droit, 2090=Global on gauche)

# Evo (milieu) - id 2088
$content = $content.Replace(
    "h='4500' id='2088' is-centered='0' is-scaled='1' param='Image/HelpIcon.png' type-v2='bitmap' w='2222' x='88333' y='3000'",
    "h='3636' id='2088' is-centered='0' is-scaled='1' param='Image/HelpIcon.png' type-v2='bitmap' w='2222' x='88333' y='3632'"
)

# Retard (droit) - id 2089
$content = $content.Replace(
    "h='4500' id='2089' is-centered='0' is-scaled='1' param='Image/HelpIcon.png' type-v2='bitmap' w='2222' x='88333' y='3000'",
    "h='3636' id='2089' is-centered='0' is-scaled='1' param='Image/HelpIcon.png' type-v2='bitmap' w='2222' x='88333' y='3632'"
)

# Global (gauche) - id 2090
$content = $content.Replace(
    "h='4500' id='2090' is-centered='0' is-scaled='1' param='Image/HelpIcon.png' type-v2='bitmap' w='2222' x='88333' y='3000'",
    "h='3636' id='2090' is-centered='0' is-scaled='1' param='Image/HelpIcon.png' type-v2='bitmap' w='2222' x='88333' y='3542'"
)

[System.IO.File]::WriteAllBytes($twbFile, $utf8.GetBytes($content))
Write-Host "TWB updated"

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
