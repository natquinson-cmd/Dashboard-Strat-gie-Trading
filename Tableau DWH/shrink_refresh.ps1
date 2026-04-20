Add-Type -AssemblyName System.IO.Compression.FileSystem

$twbxPath = 'C:\Users\quinson\Desktop\Claude\Dasboard suivi projet DataWarehouse.twbx'
$tempDir = 'C:\Users\quinson\Desktop\Claude\Tableau DWH\twbx_shrink'
if (Test-Path $tempDir) { Remove-Item $tempDir -Recurse -Force }
[System.IO.Compression.ZipFile]::ExtractToDirectory($twbxPath, $tempDir)

$twbFile = (Get-ChildItem -Path $tempDir -Filter "*.twb" | Select-Object -First 1).FullName
$bytes = [System.IO.File]::ReadAllBytes($twbFile)
$utf8 = New-Object System.Text.UTF8Encoding($false)
$content = $utf8.GetString($bytes)

# Reduce font size 11 -> 9 in the Dernier refresh worksheet
$content = $content.Replace(
    "<run fontsize='11'>Dernier Snapshot : </run>",
    "<run fontsize='9'>Dernier Snapshot : </run>"
)
$content = $content.Replace(
    "<run fontname='Tableau Bold' fontsize='11'><![CDATA[<[sqlproxy.1yiv2z00jebo4919a1ffq12saj0f].[none:DateDujour:ok]>]]></run>",
    "<run fontname='Tableau Bold' fontsize='9'><![CDATA[<[sqlproxy.1yiv2z00jebo4919a1ffq12saj0f].[none:DateDujour:ok]>]]></run>"
)

# Shrink all Dernier refresh zones: h=4545->3636, keep right edge at 98889
# w=7722 x=91167 -> w=6200 x=92689
$content = $content.Replace(
    "h='4545' id='619' name='Dernier refresh' show-title='false' w='7722' x='91167' y='4545'",
    "h='3636' id='619' name='Dernier refresh' show-title='false' w='6200' x='92689' y='5000'"
)
# w=7889 x=91000 -> w=6200 x=92689
$content = $content.Replace(
    "h='4545' id='619' name='Dernier refresh' show-title='false' w='7889' x='91000' y='4545'",
    "h='3636' id='619' name='Dernier refresh' show-title='false' w='6200' x='92689' y='5000'"
)
# w=7833 x=91056 -> w=6200 x=92689 (id=399)
$content = $content.Replace(
    "h='4545' id='399' name='Dernier refresh' show-title='false' w='7833' x='91056' y='4545'",
    "h='3636' id='399' name='Dernier refresh' show-title='false' w='6200' x='92689' y='5000'"
)

# Same for fixed-size phone zones
$content = $content.Replace(
    "h='4545' id='619' is-fixed='true' name='Dernier refresh' show-title='false' w='7722' x='91167' y='4545'",
    "h='3636' id='619' is-fixed='true' name='Dernier refresh' show-title='false' w='6200' x='92689' y='5000'"
)
$content = $content.Replace(
    "h='4545' id='619' is-fixed='true' name='Dernier refresh' show-title='false' w='7889' x='91000' y='4545'",
    "h='3636' id='619' is-fixed='true' name='Dernier refresh' show-title='false' w='6200' x='92689' y='5000'"
)
$content = $content.Replace(
    "h='4545' id='399' is-fixed='true' name='Dernier refresh' show-title='false' w='7833' x='91056' y='4545'",
    "h='3636' id='399' is-fixed='true' name='Dernier refresh' show-title='false' w='6200' x='92689' y='5000'"
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
