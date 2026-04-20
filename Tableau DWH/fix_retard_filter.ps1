Add-Type -AssemblyName System.IO.Compression.FileSystem
Add-Type -AssemblyName System.Drawing

$twbxPath = 'C:\Users\quinson\Desktop\Claude\Dasboard suivi projet DataWarehouse.twbx'
$tempDir = 'C:\Users\quinson\Desktop\Claude\Tableau DWH\twbx_retard'
if (Test-Path $tempDir) { Remove-Item $tempDir -Recurse -Force }
[System.IO.Compression.ZipFile]::ExtractToDirectory($twbxPath, $tempDir)
Write-Host "Extracted"

# Create rounded filter frame for Retard (w=11222, h=7182)
# 11222/100000 * 1800 = 202 px, 7182/100000 * 1100 = 79 px
$width = 202
$height = 79
$cornerRadius = 16
$gray = [System.Drawing.Color]::FromArgb(230, 230, 230)

$bmp = New-Object System.Drawing.Bitmap($width, $height, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
$g.Clear([System.Drawing.Color]::Transparent)

$path = New-Object System.Drawing.Drawing2D.GraphicsPath
$r = $cornerRadius
$path.AddArc(0, 0, $r * 2, $r * 2, 180, 90)
$path.AddArc($width - $r * 2, 0, $r * 2, $r * 2, 270, 90)
$path.AddArc($width - $r * 2, $height - $r * 2, $r * 2, $r * 2, 0, 90)
$path.AddArc(0, $height - $r * 2, $r * 2, $r * 2, 90, 90)
$path.CloseFigure()

$brush = New-Object System.Drawing.SolidBrush($gray)
$g.FillPath($brush, $path)
$brush.Dispose()
$path.Dispose()
$g.Dispose()

$outPath = "$tempDir\Image\Cadre Filtres Retard.png"
$bmp.Save($outPath, [System.Drawing.Imaging.ImageFormat]::Png)
$bmp.Dispose()
Write-Host "Created: Cadre Filtres Retard.png ($width x $height)"

# Replace empty zone in TWB
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

    if ($lines[$i] -match "h='7182' id='1112' type-v2='empty' w='11222'") {
        $newLines.Add("        <zone h='7182' id='1112' is-centered='0' is-scaled='1' param='Image/Cadre Filtres Retard.png' type-v2='bitmap' w='11222' x='1167' y='11364' />")
        $skip = 7
        $replaced++
        Write-Host "Replaced zone at line $($i+1)"
    }
    else {
        $newLines.Add($lines[$i])
    }
}

Write-Host "Total replaced: $replaced"

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
