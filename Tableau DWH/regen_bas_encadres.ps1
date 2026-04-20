Add-Type -AssemblyName System.Drawing

$imgPath = "C:\Users\quinson\Desktop\Claude\Tableau DWH\twbx_extracted\Image"

# Colors - original card color #0f172a
$cardColor    = [System.Drawing.Color]::FromArgb(255, 15, 23, 42)     # #0f172a
$borderIndigo = [System.Drawing.Color]::FromArgb(180, 99, 102, 241)   # #6366f1
$glowSubtle   = [System.Drawing.Color]::FromArgb(35, 99, 102, 241)
$shadowColor  = [System.Drawing.Color]::FromArgb(80, 0, 0, 0)

function New-RoundedRectPath {
    param([float]$x, [float]$y, [float]$w, [float]$h, [float]$r)
    $path = New-Object System.Drawing.Drawing2D.GraphicsPath
    $d = $r * 2
    $path.AddArc($x, $y, $d, $d, 180, 90)
    $path.AddArc($x + $w - $d, $y, $d, $d, 270, 90)
    $path.AddArc($x + $w - $d, $y + $h - $d, $d, $d, 0, 90)
    $path.AddArc($x, $y + $h - $d, $d, $d, 90, 90)
    $path.CloseFigure()
    return $path
}

function New-EncadreImage {
    param([string]$name, [int]$w, [int]$h)
    $filePath = Join-Path $imgPath $name
    $bmp = New-Object System.Drawing.Bitmap($w, $h)
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $g.Clear([System.Drawing.Color]::Transparent)
    $cornerRadius = 12
    $margin = 4
    # Shadow
    $sp = New-RoundedRectPath ($margin) ($margin + 2) ($w - $margin * 2) ($h - $margin * 2) $cornerRadius
    $sb = New-Object System.Drawing.SolidBrush($shadowColor)
    $g.FillPath($sb, $sp); $sb.Dispose(); $sp.Dispose()
    # Glow
    $gp = New-RoundedRectPath ($margin - 2) ($margin - 2) ($w - $margin * 2 + 4) ($h - $margin * 2 + 4) ($cornerRadius + 2)
    $gb = New-Object System.Drawing.SolidBrush($glowSubtle)
    $g.FillPath($gb, $gp); $gb.Dispose(); $gp.Dispose()
    # Card fill
    $cp = New-RoundedRectPath $margin $margin ($w - $margin * 2) ($h - $margin * 2) $cornerRadius
    $cb = New-Object System.Drawing.SolidBrush($cardColor)
    $g.FillPath($cb, $cp); $cb.Dispose()
    # Border
    $bp = New-Object System.Drawing.Pen($borderIndigo, 1.5)
    $g.DrawPath($bp, $cp); $bp.Dispose(); $cp.Dispose()
    $g.Dispose()
    $bmp.Save($filePath, [System.Drawing.Imaging.ImageFormat]::Png)
    $bmp.Dispose()
    Write-Host "  OK: $name ($w x $h)"
}

Write-Host "=== Regenerating Page 1 bottom encadres ==="
New-EncadreImage "Encadre milieu Page 1.png"    1365 226
New-EncadreImage "Encadre bas gauche Page1.png"  1268 319
New-EncadreImage "Encadre bas droite Page1.png"  487  323
Write-Host "Done!"
