Add-Type -AssemblyName System.IO.Compression.FileSystem

$tempDir = 'C:\Users\quinson\Desktop\Claude\Tableau DWH\twbx_debug'
if (Test-Path $tempDir) { Remove-Item $tempDir -Recurse -Force }

$twbxPath = 'C:\Users\quinson\Desktop\Claude\Dasboard suivi projet DataWarehouse.twbx'
[System.IO.Compression.ZipFile]::ExtractToDirectory($twbxPath, $tempDir)

$twbFile = (Get-ChildItem -Path $tempDir -Filter "*.twb" | Select-Object -First 1).FullName
$lines = [System.IO.File]::ReadAllLines($twbFile, [System.Text.Encoding]::UTF8)

$newLines = New-Object System.Collections.Generic.List[string]
$skip = 0
$replaced = 0

for ($i = 0; $i -lt $lines.Count; $i++) {
    if ($skip -gt 0) {
        $skip--
        continue
    }

    # Match first zone: empty w='33778'
    if ($lines[$i] -match "h='6182' id='1102' type-v2='empty' w='33778'") {
        $newLines.Add("        <zone h='6182' id='1102' is-centered='0' is-scaled='1' param='Image/Cadre Filtres Evo.png' type-v2='bitmap' w='33778' x='18278' y='8273' />")
        # Skip the next 6 lines (zone-style block + closing tag)
        $skip = 7
        $replaced++
        Write-Host "Replaced zone at line $($i+1) -> Cadre Filtres Evo.png"
    }
    # Match second zone: empty w='20111'
    elseif ($lines[$i] -match "h='6182' id='1102' type-v2='empty' w='20111'") {
        $newLines.Add("        <zone h='6182' id='1102' is-centered='0' is-scaled='1' param='Image/Cadre Filtres Statuts.png' type-v2='bitmap' w='20111' x='18611' y='8909' />")
        $skip = 7
        $replaced++
        Write-Host "Replaced zone at line $($i+1) -> Cadre Filtres Statuts.png"
    }
    else {
        $newLines.Add($lines[$i])
    }
}

Write-Host "Total replaced: $replaced"

# Write back with UTF-8 no BOM, CRLF
$utf8 = New-Object System.Text.UTF8Encoding($false)
$output = [string]::Join("`r`n", $newLines.ToArray())
[System.IO.File]::WriteAllBytes($twbFile, $utf8.GetBytes($output))

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
Remove-Item $tempDir -Recurse -Force

Write-Host "TWBX repackaged: $twbxPath"
