Add-Type -AssemblyName System.Drawing

$imgPath = "C:\Users\quinson\Desktop\Claude\Tableau DWH\twbx_extracted\Image"

# Colors
$cardColor    = [System.Drawing.Color]::FromArgb(255, 15, 23, 42)     # #0f172a
$borderIndigo = [System.Drawing.Color]::FromArgb(180, 99, 102, 241)   # #6366f1
$glowSubtle   = [System.Drawing.Color]::FromArgb(35, 99, 102, 241)
$shadowColor  = [System.Drawing.Color]::FromArgb(80, 0, 0, 0)

# Glossy highlight colors
$glossyTop    = [System.Drawing.Color]::FromArgb(30, 148, 163, 255)   # light blue tint, subtle
$glossyMid    = [System.Drawing.Color]::FromArgb(0, 148, 163, 255)    # fully transparent

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

function New-GlossyEncadre {
    param([string]$name, [int]$w, [int]$h)
    $filePath = Join-Path $imgPath $name
    $bmp = New-Object System.Drawing.Bitmap($w, $h)
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $g.Clear([System.Drawing.Color]::Transparent)

    $cornerRadius = 10
    $margin = 4

    [float]$rx = $margin
    [float]$ry = $margin
    [float]$rw = $w - $margin * 2
    [float]$rh = $h - $margin * 2

    # Shadow (offset down 2px)
    $sp = New-RoundedRectPath $rx ($ry + 2) $rw $rh $cornerRadius
    $sb = New-Object System.Drawing.SolidBrush($shadowColor)
    $g.FillPath($sb, $sp); $sb.Dispose(); $sp.Dispose()

    # Outer glow
    $gp = New-RoundedRectPath ($rx - 1) ($ry - 1) ($rw + 2) ($rh + 2) ($cornerRadius + 1)
    $gb = New-Object System.Drawing.SolidBrush($glowSubtle)
    $g.FillPath($gb, $gp); $gb.Dispose(); $gp.Dispose()

    # Card fill
    $cp = New-RoundedRectPath $rx $ry $rw $rh $cornerRadius
    $cb = New-Object System.Drawing.SolidBrush($cardColor)
    $g.FillPath($cb, $cp); $cb.Dispose()

    # Glossy highlight on top half - linear gradient
    $clipState = $g.Save()
    $g.SetClip($cp)
    [float]$glossyBottom = $ry + ($rh * 0.5)
    $pt1 = New-Object System.Drawing.PointF($rx, $ry)
    $pt2 = New-Object System.Drawing.PointF($rx, $glossyBottom)
    $glossyRect = New-Object System.Drawing.RectangleF($rx, $ry, $rw, ($rh * 0.5))
    $glossyBrush = New-Object System.Drawing.Drawing2D.LinearGradientBrush($pt1, $pt2, $glossyTop, $glossyMid)
    $g.FillRectangle($glossyBrush, $glossyRect)
    $glossyBrush.Dispose()
    $g.Restore($clipState)

    # Border
    $bp = New-Object System.Drawing.Pen($borderIndigo, 1.5)
    $g.DrawPath($bp, $cp); $bp.Dispose()
    $cp.Dispose()

    # Subtle inner highlight line at top (1px, lighter)
    $innerHighlight = [System.Drawing.Color]::FromArgb(20, 200, 210, 255)
    $hp = New-Object System.Drawing.Pen($innerHighlight, 1)
    $innerPath = New-RoundedRectPath ($rx + 1.5) ($ry + 1.5) ($rw - 3) ($rh - 3) ($cornerRadius - 1)
    $clipState2 = $g.Save()
    [float]$topClipH = $rh * 0.35
    $topClip = New-Object System.Drawing.RectangleF($rx, $ry, $rw, $topClipH)
    $g.SetClip($topClip)
    $g.DrawPath($hp, $innerPath)
    $g.Restore($clipState2)
    $hp.Dispose()
    $innerPath.Dispose()

    $g.Dispose()
    $bmp.Save($filePath, [System.Drawing.Imaging.ImageFormat]::Png)
    $bmp.Dispose()
    Write-Host "  OK: $name ($w x $h)"
}

Write-Host "=== Generating glossy Cadre Statut encadres ==="
New-GlossyEncadre "Encadre Cadre Statut.png" 230 180
Write-Host "Done!"
