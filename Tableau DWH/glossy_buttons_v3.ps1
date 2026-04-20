Add-Type -AssemblyName System.IO.Compression.FileSystem
Add-Type -AssemblyName System.Drawing

$twbxPath = 'C:\Users\quinson\Desktop\Claude\Dasboard suivi projet DataWarehouse.twbx'
$tempDir = 'C:\Users\quinson\Desktop\Claude\Tableau DWH\twbx_glossy3'
if (Test-Path $tempDir) { Remove-Item $tempDir -Recurse -Force }
[System.IO.Compression.ZipFile]::ExtractToDirectory($twbxPath, $tempDir)
Write-Host "Extracted"

# Text positions in Tableau coords within button zone (x=55556, w=32222):
# "Suivi Global":    x=58111, w=6111  -> center = 61166, relative = (61166-55556)/32222 = 17.4%
# "Suivi Evolution": x=67222, w=8889  -> center = 71666, relative = (71666-55556)/32222 = 50.0%
# "Suivi Retard":    x=77389, w=8889  -> center = 81833, relative = (81833-55556)/32222 = 81.5%

function Create-GlossyButton($width, $height, $activeCenterPct, $activeWidth, $outPath) {
    $bmp = New-Object System.Drawing.Bitmap($width, $height, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $g.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
    $g.Clear([System.Drawing.Color]::Transparent)

    $cornerOuter = 10
    $cornerInner = 7
    $padV = 4

    # === OUTER BAR ===
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

    # Glossy shine
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

    $borderPen = New-Object System.Drawing.Pen([System.Drawing.Color]::FromArgb(35, 0, 0, 0), 1)
    $g.DrawPath($borderPen, $outerPath)
    $borderPen.Dispose()
    $outerPath.Dispose()

    # === ACTIVE TAB centered on text ===
    $activeCenterX = [int]($width * $activeCenterPct)
    $ax = [int]($activeCenterX - $activeWidth / 2)
    # Clamp to stay inside outer bar
    if ($ax -lt $padV) { $ax = $padV }
    if ($ax + $activeWidth -gt $width - $padV) { $ax = $width - $padV - $activeWidth }

    $ay = $padV
    $ah = $height - $padV * 2
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

    # Shine on active
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

    $g.Dispose()
    $bmp.Save($outPath, [System.Drawing.Imaging.ImageFormat]::Png)
    $bmp.Dispose()
    Write-Host "Created: $(Split-Path $outPath -Leaf) ($width x $height), active center=$([int]($activeCenterPct*100))%"
}

$imgDir = "$tempDir\Image"

# 3-tab buttons (580px wide, 55px tall), active width 175px
Create-GlossyButton 580 55 0.174 175 "$imgDir\Bouton gauche.png"   # Suivi Global active
Create-GlossyButton 580 55 0.500 175 "$imgDir\Bouton milieu.png"   # Suivi Evolution active
Create-GlossyButton 580 55 0.815 175 "$imgDir\Bouton droit.png"    # Suivi Retard active

# Single-tab button (185px wide, 50px tall), centered
Create-GlossyButton 185 50 0.500 170 "$imgDir\Bouton seul.png"     # Retour Evolution active

Write-Host "All buttons created"

# ===== Repackage (no TWB changes needed, already done in previous run) =====
$tempZip = "$tempDir.zip"
if (Test-Path $tempZip) { Remove-Item $tempZip -Force }
[System.IO.Compression.ZipFile]::CreateFromDirectory($tempDir, $tempZip)
Copy-Item $tempZip $twbxPath -Force
Remove-Item $tempZip -Force
Remove-Item $tempDir -Recurse -Force

Write-Host "TWBX repackaged: $twbxPath"
