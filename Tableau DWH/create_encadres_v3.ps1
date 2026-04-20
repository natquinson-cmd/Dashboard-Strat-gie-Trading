Add-Type -AssemblyName System.IO.Compression.FileSystem
Add-Type -AssemblyName System.Drawing

$twbxPath = 'C:\Users\quinson\Desktop\Claude\Dasboard suivi projet DataWarehouse.twbx'
$tempDir = 'C:\Users\quinson\Desktop\Claude\Tableau DWH\twbx_enc3'
if (Test-Path $tempDir) { Remove-Item $tempDir -Recurse -Force }
[System.IO.Compression.ZipFile]::ExtractToDirectory($twbxPath, $tempDir)
Write-Host "Extracted"

$imgDir = "$tempDir\Image"

function Create-ReliefEncadre($width, $height, $outPath) {
    $bmp = New-Object System.Drawing.Bitmap($width, $height, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $g.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
    $g.Clear([System.Drawing.Color]::Transparent)

    # Card fills almost entirely, tiny margin for shadow
    $margin = 3
    $shadowDrop = 4
    $cornerRadius = 24
    $cardX = $margin
    $cardY = $margin
    $cardW = $width - $margin * 2 - $shadowDrop
    $cardH = $height - $margin * 2 - $shadowDrop

    # === SHADOW (subtle, offset bottom-right) ===
    for ($s = 6; $s -ge 1; $s -= 1) {
        $alpha = [int](12 + (6 - $s) * 4)
        if ($alpha -gt 35) { $alpha = 35 }
        $shadowBrush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb($alpha, 100, 110, 130))
        $sx = $cardX + $shadowDrop * (7 - $s) / 6 + $s / 2
        $sy = $cardY + $shadowDrop * (7 - $s) / 6 + $s / 2
        $sw = $cardW + $s
        $sh = $cardH + $s
        $r = $cornerRadius + [int]($s / 2)

        $shadowPath = New-Object System.Drawing.Drawing2D.GraphicsPath
        $shadowPath.AddArc($sx, $sy, $r * 2, $r * 2, 180, 90)
        $shadowPath.AddArc($sx + $sw - $r * 2, $sy, $r * 2, $r * 2, 270, 90)
        $shadowPath.AddArc($sx + $sw - $r * 2, $sy + $sh - $r * 2, $r * 2, $r * 2, 0, 90)
        $shadowPath.AddArc($sx, $sy + $sh - $r * 2, $r * 2, $r * 2, 90, 90)
        $shadowPath.CloseFigure()
        $g.FillPath($shadowBrush, $shadowPath)
        $shadowBrush.Dispose()
        $shadowPath.Dispose()
    }

    # === CARD (white) ===
    $cardPath = New-Object System.Drawing.Drawing2D.GraphicsPath
    $r = $cornerRadius
    $cardPath.AddArc($cardX, $cardY, $r * 2, $r * 2, 180, 90)
    $cardPath.AddArc($cardX + $cardW - $r * 2, $cardY, $r * 2, $r * 2, 270, 90)
    $cardPath.AddArc($cardX + $cardW - $r * 2, $cardY + $cardH - $r * 2, $r * 2, $r * 2, 0, 90)
    $cardPath.AddArc($cardX, $cardY + $cardH - $r * 2, $r * 2, $r * 2, 90, 90)
    $cardPath.CloseFigure()

    $cardBrush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::White)
    $g.FillPath($cardBrush, $cardPath)
    $cardBrush.Dispose()

    # Subtle border
    $borderPen = New-Object System.Drawing.Pen([System.Drawing.Color]::FromArgb(20, 0, 0, 0), 1)
    $g.DrawPath($borderPen, $cardPath)
    $borderPen.Dispose()

    $cardPath.Dispose()
    $g.Dispose()
    $bmp.Save($outPath, [System.Drawing.Imaging.ImageFormat]::Png)
    $bmp.Dispose()
}

# Map encadre keywords to 2x pixel dimensions
$encadreDims = @{
    "Haut Gauche" = @(1702, 826)
    "Haut Milieu" = @(1174, 776)
    "Haut Droite" = @(844, 850)
    "milieu"      = @(3572, 642)
    "bas gauche"  = @(2682, 654)
    "bas droite"  = @(1112, 626)
}

$encFiles = Get-ChildItem $imgDir -Filter "Encadr*"
foreach ($f in $encFiles) {
    foreach ($key in $encadreDims.Keys) {
        if ($f.Name -match [regex]::Escape($key)) {
            $dims = $encadreDims[$key]
            Remove-Item $f.FullName -Force
            Create-ReliefEncadre $dims[0] $dims[1] $f.FullName
            Write-Host "Replaced: $($f.Name) -> $($dims[0])x$($dims[1]) ($((Get-Item $f.FullName).Length) bytes)"
            break
        }
    }
}

# Repackage
$tempZip = "$tempDir.zip"
if (Test-Path $tempZip) { Remove-Item $tempZip -Force }
[System.IO.Compression.ZipFile]::CreateFromDirectory($tempDir, $tempZip)
Copy-Item $tempZip $twbxPath -Force
Remove-Item $tempZip -Force
Remove-Item $tempDir -Recurse -Force

Write-Host "TWBX repackaged"
