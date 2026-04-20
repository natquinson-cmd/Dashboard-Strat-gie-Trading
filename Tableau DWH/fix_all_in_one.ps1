Add-Type -AssemblyName System.IO.Compression.FileSystem
Add-Type -AssemblyName System.Drawing

$twbxPath = 'C:\Users\quinson\Desktop\Claude\Dasboard suivi projet DataWarehouse.twbx'
$tempDir = 'C:\Users\quinson\Desktop\Claude\Tableau DWH\twbx_final'
if (Test-Path $tempDir) { Remove-Item $tempDir -Recurse -Force }
[System.IO.Compression.ZipFile]::ExtractToDirectory($twbxPath, $tempDir)
Write-Host "Extracted"

# ===== 1. Make logo transparent =====
$logoPath = "$tempDir\Image\Logo EPFL.png"
$src = New-Object System.Drawing.Bitmap($logoPath)
$dst = New-Object System.Drawing.Bitmap($src.Width, $src.Height, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
for ($y = 0; $y -lt $src.Height; $y++) {
    for ($x = 0; $x -lt $src.Width; $x++) {
        $pixel = $src.GetPixel($x, $y)
        if ($pixel.R -gt 240 -and $pixel.G -gt 240 -and $pixel.B -gt 240) {
            $dst.SetPixel($x, $y, [System.Drawing.Color]::FromArgb(0, 255, 255, 255))
        } else {
            $dst.SetPixel($x, $y, $pixel)
        }
    }
}
$src.Dispose()
$dst.Save($logoPath, [System.Drawing.Imaging.ImageFormat]::Png)
$dst.Dispose()
Write-Host "Logo made transparent"

# ===== 2. Create rounded filter frame images =====
function Create-RoundedRect($width, $height, $cornerRadius, $bgColor, $outPath) {
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

    $brush = New-Object System.Drawing.SolidBrush($bgColor)
    $g.FillPath($brush, $path)
    $brush.Dispose()
    $path.Dispose()
    $g.Dispose()
    $bmp.Save($outPath, [System.Drawing.Imaging.ImageFormat]::Png)
    $bmp.Dispose()
    Write-Host "Created: $outPath ($width x $height)"
}

$gray = [System.Drawing.Color]::FromArgb(230, 230, 230)
Create-RoundedRect 608 68 16 $gray "$tempDir\Image\Cadre Filtres Evo.png"
Create-RoundedRect 362 68 16 $gray "$tempDir\Image\Cadre Filtres Statuts.png"

# ===== 3. Update TWB - replace empty zones with bitmap zones =====
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

    if ($lines[$i] -match "h='6182' id='1102' type-v2='empty' w='33778'") {
        $newLines.Add("        <zone h='6182' id='1102' is-centered='0' is-scaled='1' param='Image/Cadre Filtres Evo.png' type-v2='bitmap' w='33778' x='18278' y='8273' />")
        $skip = 7
        $replaced++
        Write-Host "Replaced zone at line $($i+1) -> Cadre Filtres Evo.png"
    }
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

Write-Host "Total zones replaced: $replaced"

# Remove background-color #faf5f4 from logo zones
$output = [string]::Join("`r`n", $newLines.ToArray())
$before = $output.Length
$output = $output.Replace("            <format attr='background-color' value='#faf5f4' />`r`n", "")
$after = $output.Length
if ($before -ne $after) { Write-Host "Removed background-color #faf5f4 from logo zones" }

$utf8 = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllBytes($twbFile, $utf8.GetBytes($output))

# Validate XML
try {
    $xml = New-Object System.Xml.XmlDocument
    $xml.Load($twbFile)
    Write-Host "XML: OK"
} catch {
    Write-Host "XML ERROR: $_"
}

# ===== 4. Repackage =====
$tempZip = "$tempDir.zip"
if (Test-Path $tempZip) { Remove-Item $tempZip -Force }
[System.IO.Compression.ZipFile]::CreateFromDirectory($tempDir, $tempZip)
Copy-Item $tempZip $twbxPath -Force
Remove-Item $tempZip -Force
Remove-Item $tempDir -Recurse -Force

Write-Host "TWBX repackaged: $twbxPath"
