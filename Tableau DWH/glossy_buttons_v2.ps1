Add-Type -AssemblyName System.IO.Compression.FileSystem
Add-Type -AssemblyName System.Drawing

$twbxPath = 'C:\Users\quinson\Desktop\Claude\Dasboard suivi projet DataWarehouse.twbx'
$tempDir = 'C:\Users\quinson\Desktop\Claude\Tableau DWH\twbx_glossy2'
if (Test-Path $tempDir) { Remove-Item $tempDir -Recurse -Force }
[System.IO.Compression.ZipFile]::ExtractToDirectory($twbxPath, $tempDir)
Write-Host "Extracted"

# ===== 1. Create glossy button images (shorter) =====
function Create-GlossyButton($width, $height, $activePos, $activeWidth, $outPath) {
    $bmp = New-Object System.Drawing.Bitmap($width, $height, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $g.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
    $g.Clear([System.Drawing.Color]::Transparent)

    $cornerOuter = 10
    $cornerInner = 7
    $pad = 4

    # === OUTER BAR (glossy gradient) ===
    $outerPath = New-Object System.Drawing.Drawing2D.GraphicsPath
    $r = $cornerOuter
    $outerPath.AddArc(0, 0, $r * 2, $r * 2, 180, 90)
    $outerPath.AddArc($width - $r * 2, 0, $r * 2, $r * 2, 270, 90)
    $outerPath.AddArc($width - $r * 2, $height - $r * 2, $r * 2, $r * 2, 0, 90)
    $outerPath.AddArc(0, $height - $r * 2, $r * 2, $r * 2, 90, 90)
    $outerPath.CloseFigure()

    $gradBrush = New-Object System.Drawing.Drawing2D.LinearGradientBrush(
        (New-Object System.Drawing.Rectangle(0, 0, $width, $height)),
        [System.Drawing.Color]::FromArgb(255, 232, 234, 238),
        [System.Drawing.Color]::FromArgb(255, 205, 209, 216),
        [System.Drawing.Drawing2D.LinearGradientMode]::Vertical
    )
    $g.FillPath($gradBrush, $outerPath)
    $gradBrush.Dispose()

    # Glossy shine top half
    $shineH = [int]($height * 0.45)
    $shinePath = New-Object System.Drawing.Drawing2D.GraphicsPath
    $shinePath.AddArc(0, 0, $r * 2, $r * 2, 180, 90)
    $shinePath.AddArc($width - $r * 2, 0, $r * 2, $r * 2, 270, 90)
    $shinePath.AddLine($width, $shineH, 0, $shineH)
    $shinePath.CloseFigure()
    $shineBrush = New-Object System.Drawing.Drawing2D.LinearGradientBrush(
        (New-Object System.Drawing.Rectangle(0, 0, $width, $shineH)),
        [System.Drawing.Color]::FromArgb(100, 255, 255, 255),
        [System.Drawing.Color]::FromArgb(10, 255, 255, 255),
        [System.Drawing.Drawing2D.LinearGradientMode]::Vertical
    )
    $g.FillPath($shineBrush, $shinePath)
    $shineBrush.Dispose()
    $shinePath.Dispose()

    # Border
    $borderPen = New-Object System.Drawing.Pen([System.Drawing.Color]::FromArgb(35, 0, 0, 0), 1)
    $g.DrawPath($borderPen, $outerPath)
    $borderPen.Dispose()
    $outerPath.Dispose()

    # === ACTIVE TAB (white, tight) ===
    if ($activePos -ne 'none') {
        switch ($activePos) {
            'left'   { $ax = $pad }
            'center' { $ax = [int](($width - $activeWidth) / 2) }
            'right'  { $ax = $width - $activeWidth - $pad }
            'full'   { $ax = $pad; $activeWidth = $width - $pad * 2 }
        }
        $ay = $pad
        $ah = $height - $pad * 2
        $aw = $activeWidth

        $activePath = New-Object System.Drawing.Drawing2D.GraphicsPath
        $ri = $cornerInner
        $activePath.AddArc($ax, $ay, $ri * 2, $ri * 2, 180, 90)
        $activePath.AddArc($ax + $aw - $ri * 2, $ay, $ri * 2, $ri * 2, 270, 90)
        $activePath.AddArc($ax + $aw - $ri * 2, $ay + $ah - $ri * 2, $ri * 2, $ri * 2, 0, 90)
        $activePath.AddArc($ax, $ay + $ah - $ri * 2, $ri * 2, $ri * 2, 90, 90)
        $activePath.CloseFigure()

        $activeGrad = New-Object System.Drawing.Drawing2D.LinearGradientBrush(
            (New-Object System.Drawing.Rectangle($ax, $ay, $aw, $ah)),
            [System.Drawing.Color]::FromArgb(255, 255, 255, 255),
            [System.Drawing.Color]::FromArgb(255, 248, 249, 250),
            [System.Drawing.Drawing2D.LinearGradientMode]::Vertical
        )
        $g.FillPath($activeGrad, $activePath)
        $activeGrad.Dispose()

        # Shine on active tab
        $activeShineH = [int]($ah * 0.4)
        $activeShinePath = New-Object System.Drawing.Drawing2D.GraphicsPath
        $activeShinePath.AddArc($ax, $ay, $ri * 2, $ri * 2, 180, 90)
        $activeShinePath.AddArc($ax + $aw - $ri * 2, $ay, $ri * 2, $ri * 2, 270, 90)
        $activeShinePath.AddLine($ax + $aw, $ay + $activeShineH, $ax, $ay + $activeShineH)
        $activeShinePath.CloseFigure()
        $activeShine = New-Object System.Drawing.Drawing2D.LinearGradientBrush(
            (New-Object System.Drawing.Rectangle($ax, $ay, $aw, $activeShineH)),
            [System.Drawing.Color]::FromArgb(130, 255, 255, 255),
            [System.Drawing.Color]::FromArgb(0, 255, 255, 255),
            [System.Drawing.Drawing2D.LinearGradientMode]::Vertical
        )
        $g.FillPath($activeShine, $activeShinePath)
        $activeShine.Dispose()
        $activeShinePath.Dispose()

        $activeBorder = New-Object System.Drawing.Pen([System.Drawing.Color]::FromArgb(30, 0, 0, 0), 0.7)
        $g.DrawPath($activeBorder, $activePath)
        $activeBorder.Dispose()
        $activePath.Dispose()
    }

    $g.Dispose()
    $bmp.Save($outPath, [System.Drawing.Imaging.ImageFormat]::Png)
    $bmp.Dispose()
    Write-Host "Created: $(Split-Path $outPath -Leaf) ($width x $height)"
}

$imgDir = "$tempDir\Image"

# Images shorter: ~60px height, same width ratios
# Active tab width proportional to text label: ~8889/32222 of total = ~28% of width
# For 3-tab buttons (w=32222): active ~193px in a 580px image
# For seul button (w=10167): full width active

Create-GlossyButton 580 55 'left' 175 "$imgDir\Bouton gauche.png"
Create-GlossyButton 580 55 'center' 175 "$imgDir\Bouton milieu.png"
Create-GlossyButton 580 55 'right' 175 "$imgDir\Bouton droit.png"
Create-GlossyButton 185 50 'full' 0 "$imgDir\Bouton seul.png"

# ===== 2. Update TWB zone heights and Y positions =====
$twbFile = (Get-ChildItem -Path $tempDir -Filter "*.twb" | Select-Object -First 1).FullName
$bytes = [System.IO.File]::ReadAllBytes($twbFile)
$utf8 = New-Object System.Text.UTF8Encoding($false)
$content = $utf8.GetString($bytes)

# Change button heights from 9091 to 5000 and reposition Y
# milieu: y=909,h=9091 -> y=2950,h=5000
$content = $content.Replace(
    "Bouton milieu.png' type-v2='bitmap' w='32222' x='55556' y='909'",
    "Bouton milieu.png' type-v2='bitmap' w='32222' x='55556' y='2950'"
)
$content = $content.Replace(
    "h='9091' id='681' is-centered='0' is-scaled='1' param='Image/Bouton milieu.png'",
    "h='5000' id='681' is-centered='0' is-scaled='1' param='Image/Bouton milieu.png'"
)

# droit: y=909,h=9091 -> y=2950,h=5000
$content = $content.Replace(
    "Bouton droit.png' type-v2='bitmap' w='32222' x='55556' y='909'",
    "Bouton droit.png' type-v2='bitmap' w='32222' x='55556' y='2950'"
)
$content = $content.Replace(
    "h='9091' id='681' is-centered='0' is-scaled='1' param='Image/Bouton droit.png'",
    "h='5000' id='681' is-centered='0' is-scaled='1' param='Image/Bouton droit.png'"
)

# gauche: y=818,h=9091 -> y=2860,h=5000
$content = $content.Replace(
    "Bouton gauche.png' type-v2='bitmap' w='32222' x='55556' y='818'",
    "Bouton gauche.png' type-v2='bitmap' w='32222' x='55556' y='2860'"
)
$content = $content.Replace(
    "h='9091' id='811' is-centered='0' is-scaled='1' param='Image/Bouton gauche.png'",
    "h='5000' id='811' is-centered='0' is-scaled='1' param='Image/Bouton gauche.png'"
)

# seul header (Evo Statuts): y=1636,h=9091 -> y=2950,h=5000
$content = $content.Replace(
    "Bouton seul.png' type-v2='bitmap' w='10167' x='66556' y='1636'",
    "Bouton seul.png' type-v2='bitmap' w='10167' x='66556' y='2950'"
)
$content = $content.Replace(
    "h='9091' id='681' is-centered='0' is-scaled='1' param='Image/Bouton seul.png' type-v2='bitmap' w='10167'",
    "h='5000' id='681' is-centered='0' is-scaled='1' param='Image/Bouton seul.png' type-v2='bitmap' w='10167'"
)

# DON'T touch the "Voir details" button: h='5000' id='1339' w='12111' y='37182'

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

# ===== 3. Repackage =====
$tempZip = "$tempDir.zip"
if (Test-Path $tempZip) { Remove-Item $tempZip -Force }
[System.IO.Compression.ZipFile]::CreateFromDirectory($tempDir, $tempZip)
Copy-Item $tempZip $twbxPath -Force
Remove-Item $tempZip -Force
Remove-Item $tempDir -Recurse -Force

Write-Host "TWBX repackaged: $twbxPath"
