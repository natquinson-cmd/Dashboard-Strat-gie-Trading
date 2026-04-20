Add-Type -AssemblyName System.Drawing

function Create-GlossyButton($width, $height, $activePos, $activeWidth, $outPath) {
    # activePos: 'left', 'center', 'right', 'full'
    $bmp = New-Object System.Drawing.Bitmap($width, $height, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $g.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
    $g.Clear([System.Drawing.Color]::Transparent)

    $cornerOuter = 14
    $cornerInner = 10
    $pad = 6

    # === OUTER BAR (glossy gradient) ===
    $outerPath = New-Object System.Drawing.Drawing2D.GraphicsPath
    $r = $cornerOuter
    $outerPath.AddArc(0, 0, $r * 2, $r * 2, 180, 90)
    $outerPath.AddArc($width - $r * 2, 0, $r * 2, $r * 2, 270, 90)
    $outerPath.AddArc($width - $r * 2, $height - $r * 2, $r * 2, $r * 2, 0, 90)
    $outerPath.AddArc(0, $height - $r * 2, $r * 2, $r * 2, 90, 90)
    $outerPath.CloseFigure()

    # Base gradient: light gray to slightly darker
    $gradRect = New-Object System.Drawing.Rectangle(0, 0, $width, $height)
    $gradBrush = New-Object System.Drawing.Drawing2D.LinearGradientBrush(
        $gradRect,
        [System.Drawing.Color]::FromArgb(255, 228, 230, 235),  # top: lighter
        [System.Drawing.Color]::FromArgb(255, 200, 204, 212),  # bottom: slightly darker
        [System.Drawing.Drawing2D.LinearGradientMode]::Vertical
    )
    $g.FillPath($gradBrush, $outerPath)
    $gradBrush.Dispose()

    # Glossy shine on top half
    $shineHeight = [int]($height * 0.45)
    $shinePath = New-Object System.Drawing.Drawing2D.GraphicsPath
    $shinePath.AddArc(0, 0, $r * 2, $r * 2, 180, 90)
    $shinePath.AddArc($width - $r * 2, 0, $r * 2, $r * 2, 270, 90)
    $shinePath.AddLine($width, $shineHeight, 0, $shineHeight)
    $shinePath.CloseFigure()

    $shineBrush = New-Object System.Drawing.Drawing2D.LinearGradientBrush(
        (New-Object System.Drawing.Rectangle(0, 0, $width, $shineHeight)),
        [System.Drawing.Color]::FromArgb(90, 255, 255, 255),   # top: white shine
        [System.Drawing.Color]::FromArgb(10, 255, 255, 255),   # fade out
        [System.Drawing.Drawing2D.LinearGradientMode]::Vertical
    )
    $g.FillPath($shineBrush, $shinePath)
    $shineBrush.Dispose()
    $shinePath.Dispose()

    # Subtle bottom shadow line
    $shadowPen = New-Object System.Drawing.Pen([System.Drawing.Color]::FromArgb(30, 0, 0, 0), 1)
    $g.DrawPath($shadowPen, $outerPath)
    $shadowPen.Dispose()
    $outerPath.Dispose()

    # === ACTIVE TAB (white, glossy) ===
    if ($activePos -ne 'none') {
        switch ($activePos) {
            'left'   { $ax = $pad; }
            'center' { $ax = [int](($width - $activeWidth) / 2); }
            'right'  { $ax = $width - $activeWidth - $pad; }
            'full'   { $ax = $pad; $activeWidth = $width - $pad * 2; }
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

        # White gradient for active tab
        $activeGrad = New-Object System.Drawing.Drawing2D.LinearGradientBrush(
            (New-Object System.Drawing.Rectangle($ax, $ay, $aw, $ah)),
            [System.Drawing.Color]::FromArgb(255, 255, 255, 255),  # pure white top
            [System.Drawing.Color]::FromArgb(255, 245, 246, 248),  # very subtle gray bottom
            [System.Drawing.Drawing2D.LinearGradientMode]::Vertical
        )
        $g.FillPath($activeGrad, $activePath)
        $activeGrad.Dispose()

        # Glossy shine on active tab top half
        $activeShineH = [int]($ah * 0.4)
        $activeShinePath = New-Object System.Drawing.Drawing2D.GraphicsPath
        $activeShinePath.AddArc($ax, $ay, $ri * 2, $ri * 2, 180, 90)
        $activeShinePath.AddArc($ax + $aw - $ri * 2, $ay, $ri * 2, $ri * 2, 270, 90)
        $activeShinePath.AddLine($ax + $aw, $ay + $activeShineH, $ax, $ay + $activeShineH)
        $activeShinePath.CloseFigure()

        $activeShine = New-Object System.Drawing.Drawing2D.LinearGradientBrush(
            (New-Object System.Drawing.Rectangle($ax, $ay, $aw, $activeShineH)),
            [System.Drawing.Color]::FromArgb(120, 255, 255, 255),
            [System.Drawing.Color]::FromArgb(0, 255, 255, 255),
            [System.Drawing.Drawing2D.LinearGradientMode]::Vertical
        )
        $g.FillPath($activeShine, $activeShinePath)
        $activeShine.Dispose()
        $activeShinePath.Dispose()

        # Subtle border on active tab
        $activeBorder = New-Object System.Drawing.Pen([System.Drawing.Color]::FromArgb(40, 0, 0, 0), 0.8)
        $g.DrawPath($activeBorder, $activePath)
        $activeBorder.Dispose()
        $activePath.Dispose()
    }

    $g.Dispose()
    $bmp.Save($outPath, [System.Drawing.Imaging.ImageFormat]::Png)
    $bmp.Dispose()
    Write-Host "Created: $(Split-Path $outPath -Leaf) ($width x $height)"
}

$imgDir = 'C:\Users\quinson\Desktop\Claude\Tableau DWH\twbx_buttons\Image'

# Bouton gauche: 695x123, active tab on LEFT (~200px wide)
Create-GlossyButton 695 123 'left' 200 "$imgDir\Bouton gauche.png"

# Bouton milieu: 701x122, active tab in CENTER (~200px wide)
Create-GlossyButton 701 122 'center' 200 "$imgDir\Bouton milieu.png"

# Bouton droit: 688x117, active tab on RIGHT (~200px wide)
Create-GlossyButton 688 117 'right' 200 "$imgDir\Bouton droit.png"

# Bouton seul: 246x114, active tab FULL
Create-GlossyButton 246 114 'full' 0 "$imgDir\Bouton seul.png"
