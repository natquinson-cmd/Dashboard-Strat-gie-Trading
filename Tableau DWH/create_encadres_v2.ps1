Add-Type -AssemblyName System.IO.Compression.FileSystem
Add-Type -AssemblyName System.Drawing

$twbxPath = 'C:\Users\quinson\Desktop\Claude\Dasboard suivi projet DataWarehouse.twbx'
$tempDir = 'C:\Users\quinson\Desktop\Claude\Tableau DWH\twbx_enc2'
if (Test-Path $tempDir) { Remove-Item $tempDir -Recurse -Force }
[System.IO.Compression.ZipFile]::ExtractToDirectory($twbxPath, $tempDir)
Write-Host "Extracted"

# Get actual filenames from disk
$imgDir = "$tempDir\Image"
$encFiles = Get-ChildItem $imgDir -Filter "Encadr*"
Write-Host "Found $($encFiles.Count) encadre files:"
foreach ($f in $encFiles) {
    Write-Host "  $($f.Name) ($($f.Length) bytes)"
}

function Create-ReliefEncadre($width, $height, $outPath) {
    $shadowOffset = 8
    $shadowBlur = 12
    $padTotal = $shadowBlur + $shadowOffset + 4
    $totalW = $width + $padTotal * 2
    $totalH = $height + $padTotal * 2

    $bmp = New-Object System.Drawing.Bitmap($totalW, $totalH, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $g.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
    $g.Clear([System.Drawing.Color]::Transparent)

    $cornerRadius = 16
    $cardX = $padTotal
    $cardY = $padTotal
    $cardW = $width
    $cardH = $height

    # Shadow layers
    for ($s = $shadowBlur; $s -ge 1; $s -= 2) {
        $alpha = [int](18 * ($shadowBlur - $s + 1) / $shadowBlur)
        if ($alpha -gt 30) { $alpha = 30 }
        $shadowBrush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb($alpha, 80, 90, 110))
        $sx = $cardX + $shadowOffset * $s / $shadowBlur - $s
        $sy = $cardY + $shadowOffset * $s / $shadowBlur - $s
        $sw = $cardW + $s * 2
        $sh = $cardH + $s * 2
        $r = $cornerRadius + $s

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

    # Card body
    $cardPath = New-Object System.Drawing.Drawing2D.GraphicsPath
    $r = $cornerRadius
    $cardPath.AddArc($cardX, $cardY, $r * 2, $r * 2, 180, 90)
    $cardPath.AddArc($cardX + $cardW - $r * 2, $cardY, $r * 2, $r * 2, 270, 90)
    $cardPath.AddArc($cardX + $cardW - $r * 2, $cardY + $cardH - $r * 2, $r * 2, $r * 2, 0, 90)
    $cardPath.AddArc($cardX, $cardY + $cardH - $r * 2, $r * 2, $r * 2, 90, 90)
    $cardPath.CloseFigure()

    $cardGrad = New-Object System.Drawing.Drawing2D.LinearGradientBrush(
        (New-Object System.Drawing.Rectangle($cardX, $cardY, $cardW, $cardH)),
        [System.Drawing.Color]::FromArgb(255, 255, 255, 255),
        [System.Drawing.Color]::FromArgb(255, 252, 252, 254),
        [System.Drawing.Drawing2D.LinearGradientMode]::Vertical
    )
    $g.FillPath($cardGrad, $cardPath)
    $cardGrad.Dispose()

    # Top highlight
    $shineH = [int]($cardH * 0.35)
    $g.SetClip($cardPath)
    $shineBrush = New-Object System.Drawing.Drawing2D.LinearGradientBrush(
        (New-Object System.Drawing.Rectangle($cardX, $cardY, $cardW, $shineH)),
        [System.Drawing.Color]::FromArgb(60, 255, 255, 255),
        [System.Drawing.Color]::FromArgb(0, 255, 255, 255),
        [System.Drawing.Drawing2D.LinearGradientMode]::Vertical
    )
    $g.FillRectangle($shineBrush, $cardX, $cardY, $cardW, $shineH)
    $shineBrush.Dispose()
    $g.ResetClip()

    # Border
    $borderPen = New-Object System.Drawing.Pen([System.Drawing.Color]::FromArgb(25, 0, 0, 0), 1)
    $g.DrawPath($borderPen, $cardPath)
    $borderPen.Dispose()

    # Top edge highlight
    $topHighlight = New-Object System.Drawing.Pen([System.Drawing.Color]::FromArgb(80, 255, 255, 255), 1.5)
    $innerPath = New-Object System.Drawing.Drawing2D.GraphicsPath
    $ri = $cornerRadius - 1
    $innerPath.AddArc($cardX + 1, $cardY + 1, $ri * 2, $ri * 2, 180, 90)
    $innerPath.AddArc($cardX + $cardW - $ri * 2 - 1, $cardY + 1, $ri * 2, $ri * 2, 270, 90)
    $clipRect = New-Object System.Drawing.Rectangle($cardX, $cardY, $cardW, [int]($cardH * 0.5))
    $g.SetClip($clipRect)
    $g.DrawPath($topHighlight, $innerPath)
    $g.ResetClip()
    $topHighlight.Dispose()
    $innerPath.Dispose()

    $cardPath.Dispose()
    $g.Dispose()
    $bmp.Save($outPath, [System.Drawing.Imaging.ImageFormat]::Png)
    $bmp.Dispose()
}

# Map encadre names to dimensions (2x resolution)
$encadreDims = @{
    "Haut Gauche" = @(1702, 826)
    "Haut Milieu" = @(1174, 776)
    "Haut Droite" = @(844, 850)
    "milieu"      = @(3572, 642)
    "bas gauche"  = @(2682, 654)
    "bas droite"  = @(1112, 626)
}

foreach ($f in $encFiles) {
    $matched = $false
    foreach ($key in $encadreDims.Keys) {
        if ($f.Name -match [regex]::Escape($key)) {
            $dims = $encadreDims[$key]
            $outPath = $f.FullName
            Write-Host "Replacing: $($f.Name) -> ${dims[0]}x${dims[1]}"
            # Delete old file first
            Remove-Item $outPath -Force
            Create-ReliefEncadre $dims[0] $dims[1] $outPath
            # Verify
            $newImg = [System.Drawing.Image]::FromFile($outPath)
            Write-Host "  Result: $($newImg.Width)x$($newImg.Height), $((Get-Item $outPath).Length) bytes"
            $newImg.Dispose()
            $matched = $true
            break
        }
    }
    if (-not $matched) {
        Write-Host "SKIPPED: $($f.Name) (no match)"
    }
}

# Repackage
$tempZip = "$tempDir.zip"
if (Test-Path $tempZip) { Remove-Item $tempZip -Force }
[System.IO.Compression.ZipFile]::CreateFromDirectory($tempDir, $tempZip)
Copy-Item $tempZip $twbxPath -Force
Remove-Item $tempZip -Force
Remove-Item $tempDir -Recurse -Force

Write-Host "`nTWBX repackaged: $twbxPath"
