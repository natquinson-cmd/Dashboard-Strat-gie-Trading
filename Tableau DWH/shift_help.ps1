Add-Type -AssemblyName System.IO.Compression.FileSystem

$twbxPath = 'C:\Users\quinson\Desktop\Claude\Dasboard suivi projet DataWarehouse.twbx'
$tempDir = 'C:\Users\quinson\Desktop\Claude\Tableau DWH\twbx_shift'
if (Test-Path $tempDir) { Remove-Item $tempDir -Recurse -Force }
[System.IO.Compression.ZipFile]::ExtractToDirectory($twbxPath, $tempDir)

$twbFile = (Get-ChildItem -Path $tempDir -Filter "*.twb" | Select-Object -First 1).FullName
$bytes = [System.IO.File]::ReadAllBytes($twbFile)
$utf8 = New-Object System.Text.UTF8Encoding($false)
$content = $utf8.GetString($bytes)

# Shift HelpIcon bitmap zones x=88333 -> x=89500 (centered between button and Dernier Snapshot)
$content = $content.Replace(
    "id='2088' is-centered='0' is-scaled='1' param='Image/HelpIcon.png' type-v2='bitmap' w='2222' x='88333'",
    "id='2088' is-centered='0' is-scaled='1' param='Image/HelpIcon.png' type-v2='bitmap' w='2222' x='89500'"
)
$content = $content.Replace(
    "id='2089' is-centered='0' is-scaled='1' param='Image/HelpIcon.png' type-v2='bitmap' w='2222' x='88333'",
    "id='2089' is-centered='0' is-scaled='1' param='Image/HelpIcon.png' type-v2='bitmap' w='2222' x='89500'"
)
$content = $content.Replace(
    "id='2090' is-centered='0' is-scaled='1' param='Image/HelpIcon.png' type-v2='bitmap' w='2222' x='88333'",
    "id='2090' is-centered='0' is-scaled='1' param='Image/HelpIcon.png' type-v2='bitmap' w='2222' x='89500'"
)

# Also shift the underlying glossaire worksheet zones so tooltip hover stays aligned
$content = $content.Replace(
    "h='6000' id='1178' name='Glossaire Evo' show-title='false' w='2222' x='88333' y='2273'",
    "h='6000' id='1178' name='Glossaire Evo' show-title='false' w='2222' x='89500' y='2273'"
)
$content = $content.Replace(
    "h='6000' id='1182' name='Glossaire Retard' show-title='false' w='2222' x='88333' y='2273'",
    "h='6000' id='1182' name='Glossaire Retard' show-title='false' w='2222' x='89500' y='2273'"
)
$content = $content.Replace(
    "h='6000' id='1319' name='Glossaire Global' show-title='false' w='2222' x='88333' y='2273'",
    "h='6000' id='1319' name='Glossaire Global' show-title='false' w='2222' x='89500' y='2273'"
)

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
