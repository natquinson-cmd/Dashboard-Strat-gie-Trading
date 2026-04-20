Add-Type -AssemblyName System.Drawing

function Create-ReliefEncadre($width, $height, $outPath) {
    # Add padding around the card for the shadow
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

    # === SHADOW LAYERS (multiple passes for soft shadow) ===
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

    # === CARD BODY (white) ===
    $cardPath = New-Object System.Drawing.Drawing2D.GraphicsPath
    $r = $cornerRadius
    $cardPath.AddArc($cardX, $cardY, $r * 2, $r * 2, 180, 90)
    $cardPath.AddArc($cardX + $cardW - $r * 2, $cardY, $r * 2, $r * 2, 270, 90)
    $cardPath.AddArc($cardX + $cardW - $r * 2, $cardY + $cardH - $r * 2, $r * 2, $r * 2, 0, 90)
    $cardPath.AddArc($cardX, $cardY + $cardH - $r * 2, $r * 2, $r * 2, 90, 90)
    $cardPath.CloseFigure()

    # White gradient (very subtle top-to-bottom)
    $cardGrad = New-Object System.Drawing.Drawing2D.LinearGradientBrush(
        (New-Object System.Drawing.Rectangle($cardX, $cardY, $cardW, $cardH)),
        [System.Drawing.Color]::FromArgb(255, 255, 255, 255),
        [System.Drawing.Color]::FromArgb(255, 252, 252, 254),
        [System.Drawing.Drawing2D.LinearGradientMode]::Vertical
    )
    $g.FillPath($cardGrad, $cardPath)
    $cardGrad.Dispose()

    # === TOP HIGHLIGHT (glossy shine) ===
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

    # === BORDER (very subtle) ===
    $borderPen = New-Object System.Drawing.Pen([System.Drawing.Color]::FromArgb(25, 0, 0, 0), 1)
    $g.DrawPath($borderPen, $cardPath)
    $borderPen.Dispose()

    # === TOP EDGE HIGHLIGHT (white line for inset relief) ===
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
    Write-Host "Created: $(Split-Path $outPath -Leaf) ($totalW x $totalH)"
}

$imgDir = 'C:\Users\quinson\Desktop\Claude\Tableau DWH\twbx_encadres\Image'

# Zone dimensions -> pixel dimensions (2x resolution for crispness)
# Dashboard = 1800x1100, coords 0-100000
# Haut Gauche: w=47278, h=37545 -> 851x413 -> 2x = 1702x826
# Haut Milieu: w=32611, h=35273 -> 587x388 -> 2x = 1174x776
# Haut Droite: w=23444, h=38636 -> 422x425 -> 2x = 844x850
# Milieu:      w=99222, h=29182 -> 1786x321 -> 2x = 3572x642
# Bas Gauche:  w=74500, h=29727 -> 1341x327 -> 2x = 2682x654
# Bas Droite:  w=30889, h=28455 -> 556x313 -> 2x = 1112x626

Create-ReliefEncadre 1702 826 "$imgDir\Encadré Haut Gauche Page1.png"
Create-ReliefEncadre 1174 776 "$imgDir\Encadré Haut Milieu Page1.png"
Create-ReliefEncadre 844 850 "$imgDir\Encadré Haut Droite Page1.png"
Create-ReliefEncadre 3572 642 "$imgDir\Encadré milieu Page 1.png"
Create-ReliefEncadre 2682 654 "$imgDir\Encadré bas gauche Page1.png"
Create-ReliefEncadre 1112 626 "$imgDir\Encadré bas droite Page1.png"
