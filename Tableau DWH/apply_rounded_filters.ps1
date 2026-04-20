Add-Type -AssemblyName System.IO.Compression.FileSystem

$tempDir = 'C:\Users\quinson\Desktop\Claude\Tableau DWH\twbx_roundcorners'
$twbxPath = 'C:\Users\quinson\Desktop\Claude\Dasboard suivi projet DataWarehouse.twbx'

$twbFile = (Get-ChildItem -Path $tempDir -Filter "*.twb" | Select-Object -First 1).FullName
$bytes = [System.IO.File]::ReadAllBytes($twbFile)
$utf8 = New-Object System.Text.UTF8Encoding($false)
$content = $utf8.GetString($bytes)

# Replace first empty zone (Suivi Evolution) - w='33778'
$oldZone1 = @"
        <zone h='6182' id='1102' type-v2='empty' w='33778' x='18278' y='8273'>
          <zone-style>
            <format attr='border-color' value='#000000' />
            <format attr='border-style' value='none' />
            <format attr='border-width' value='0' />
            <format attr='background-color' value='#e6e6e6' />
          </zone-style>
        </zone>
"@

$newZone1 = "        <zone h='6182' id='1102' is-centered='0' is-scaled='1' param='Image/Cadre Filtres Evo.png' type-v2='bitmap' w='33778' x='18278' y='8273' />"

# Replace second empty zone (Suivi Evolution Statuts) - w='20111'
$oldZone2 = @"
        <zone h='6182' id='1102' type-v2='empty' w='20111' x='18611' y='8909'>
          <zone-style>
            <format attr='border-color' value='#000000' />
            <format attr='border-style' value='none' />
            <format attr='border-width' value='0' />
            <format attr='background-color' value='#e6e6e6' />
          </zone-style>
        </zone>
"@

$newZone2 = "        <zone h='6182' id='1102' is-centered='0' is-scaled='1' param='Image/Cadre Filtres Statuts.png' type-v2='bitmap' w='20111' x='18611' y='8909' />"

$content = $content.Replace($oldZone1, $newZone1)
$content = $content.Replace($oldZone2, $newZone2)

[System.IO.File]::WriteAllBytes($twbFile, $utf8.GetBytes($content))
Write-Host "TWB updated"

# Validate XML
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

Write-Host "TWBX repackaged: $twbxPath"
