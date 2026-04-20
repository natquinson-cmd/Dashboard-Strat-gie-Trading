Add-Type -AssemblyName System.IO.Compression.FileSystem

$twbxPath = 'C:\Users\quinson\Desktop\Claude\Dasboard suivi projet DataWarehouse.twbx'
$tempDir = 'C:\Users\quinson\Desktop\Claude\Tableau DWH\twbx_shrinklogo'
if (Test-Path $tempDir) { Remove-Item $tempDir -Recurse -Force }
[System.IO.Compression.ZipFile]::ExtractToDirectory($twbxPath, $tempDir)

$twbFile = (Get-ChildItem -Path $tempDir -Filter "*.twb" | Select-Object -First 1).FullName
$bytes = [System.IO.File]::ReadAllBytes($twbFile)
$utf8 = New-Object System.Text.UTF8Encoding($false)
$content = $utf8.GetString($bytes)

# Logo: h=7727 w=17111 x=1111 y=1364 -> reduce ~20%
# New: h=6000 w=13300 x=1500 y=2227 (centered vertically with original center ~5227)
# Old center y = 1364+3863 = 5227
# New center y = 2227+3000 = 5227 ✓

$content = $content.Replace(
    "h='7727' id='219' param='Image/Logo EPFL.png' type-v2='bitmap' w='17111' x='1111' y='1364'",
    "h='6000' id='219' param='Image/Logo EPFL.png' type-v2='bitmap' w='13300' x='1500' y='2227'"
)
$content = $content.Replace(
    "h='7727' id='219' is-fixed='true' param='Image/Logo EPFL.png' type-v2='bitmap' w='17111' x='1111' y='1364'",
    "h='6000' id='219' is-fixed='true' param='Image/Logo EPFL.png' type-v2='bitmap' w='13300' x='1500' y='2227'"
)
$content = $content.Replace(
    "h='7727' id='192' param='Image/Logo EPFL.png' type-v2='bitmap' w='17111' x='1111' y='1364'",
    "h='6000' id='192' param='Image/Logo EPFL.png' type-v2='bitmap' w='13300' x='1500' y='2227'"
)
$content = $content.Replace(
    "h='7727' id='192' is-fixed='true' param='Image/Logo EPFL.png' type-v2='bitmap' w='17111' x='1111' y='1364'",
    "h='6000' id='192' is-fixed='true' param='Image/Logo EPFL.png' type-v2='bitmap' w='13300' x='1500' y='2227'"
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
