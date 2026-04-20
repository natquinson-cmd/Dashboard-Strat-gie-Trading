Add-Type -AssemblyName System.IO.Compression.FileSystem

$tempDir = 'C:\Users\quinson\Desktop\Claude\Tableau DWH\twbx_help'
$twbxPath = 'C:\Users\quinson\Desktop\Claude\Dasboard suivi projet DataWarehouse.twbx'

$twbFile = (Get-ChildItem -Path $tempDir -Filter "*.twb" | Select-Object -First 1).FullName
$bytes = [System.IO.File]::ReadAllBytes($twbFile)
$utf8 = New-Object System.Text.UTF8Encoding($false)
$content = $utf8.GetString($bytes)

# 1. Hide the "?" text label by making it transparent (fontcolor matches background)
#    This keeps the worksheet functional (tooltip on hover) but hides the ugly "?"
#    Change in all 3 glossaire worksheets
$content = $content.Replace(
    "<run bold='true' fontname='Tableau Bold' fontsize='48'>?</run>",
    "<run bold='true' fontcolor='#ffffff00' fontname='Tableau Bold' fontsize='1'>?</run>"
)

# 2. Add bitmap zones BEFORE each glossaire worksheet zone
#    Glossaire zones are at: h='6000', w='2222', x='88333', y='2273'
#    Icon zone: same position, same size, as bitmap
#    The bitmap will be visually on top but the worksheet zone underneath handles hover/tooltip

# For desktop zones (not fixed-size)
$content = $content.Replace(
    "<zone h='6000' id='1178' name='Glossaire Evo' show-title='false' w='2222' x='88333' y='2273' />",
    "<zone h='4500' id='2088' is-centered='0' is-scaled='1' param='Image/HelpIcon.png' type-v2='bitmap' w='2222' x='88333' y='3000' />`r`n        <zone h='6000' id='1178' name='Glossaire Evo' show-title='false' w='2222' x='88333' y='2273' />"
)

$content = $content.Replace(
    "<zone h='6000' id='1182' name='Glossaire Retard' show-title='false' w='2222' x='88333' y='2273' />",
    "<zone h='4500' id='2089' is-centered='0' is-scaled='1' param='Image/HelpIcon.png' type-v2='bitmap' w='2222' x='88333' y='3000' />`r`n        <zone h='6000' id='1182' name='Glossaire Retard' show-title='false' w='2222' x='88333' y='2273' />"
)

$content = $content.Replace(
    "<zone h='6000' id='1319' name='Glossaire Global' show-title='false' w='2222' x='88333' y='2273' />",
    "<zone h='4500' id='2090' is-centered='0' is-scaled='1' param='Image/HelpIcon.png' type-v2='bitmap' w='2222' x='88333' y='3000' />`r`n        <zone h='6000' id='1319' name='Glossaire Global' show-title='false' w='2222' x='88333' y='2273' />"
)

[System.IO.File]::WriteAllBytes($twbFile, $utf8.GetBytes($content))
Write-Host "TWB updated"

# Validate
try {
    $xml = New-Object System.Xml.XmlDocument
    $xml.Load($twbFile)
    Write-Host "XML: OK"
} catch {
    Write-Host "XML ERROR: $_"
}

# Repackage
$tempZip = "$tempDir.zip"
if (Test-Path $tempZip) { Remove-Item $tempZip -Force }
[System.IO.Compression.ZipFile]::CreateFromDirectory($tempDir, $tempZip)
Copy-Item $tempZip $twbxPath -Force
Remove-Item $tempZip -Force
Remove-Item $tempDir -Recurse -Force

Write-Host "TWBX repackaged: $twbxPath"
