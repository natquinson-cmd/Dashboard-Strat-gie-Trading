Add-Type -AssemblyName System.Drawing

# Create a modern circular help icon - glossy style matching buttons
$size = 120  # High res, Tableau will scale down
$bmp = New-Object System.Drawing.Bitmap($size, $size, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
$g.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::AntiAliasGridFit
$g.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
$g.Clear([System.Drawing.Color]::Transparent)

$margin = 4
$circleSize = $size - $margin * 2

# === CIRCLE BACKGROUND (glossy gradient matching button theme) ===
$circlePath = New-Object System.Drawing.Drawing2D.GraphicsPath
$circlePath.AddEllipse($margin, $margin, $circleSize, $circleSize)

# Base gradient: steel blue-gray
$gradBrush = New-Object System.Drawing.Drawing2D.LinearGradientBrush(
    (New-Object System.Drawing.Rectangle($margin, $margin, $circleSize, $circleSize)),
    [System.Drawing.Color]::FromArgb(255, 120, 130, 150),  # top: medium blue-gray
    [System.Drawing.Color]::FromArgb(255, 85, 95, 115),    # bottom: darker
    [System.Drawing.Drawing2D.LinearGradientMode]::Vertical
)
$g.FillPath($gradBrush, $circlePath)
$gradBrush.Dispose()

# Glossy shine on top half
$shineH = [int]($circleSize * 0.45)
$shinePath = New-Object System.Drawing.Drawing2D.GraphicsPath
$shinePath.AddArc($margin, $margin, $circleSize, $circleSize, 180, 180)
$shinePath.AddLine($margin + $circleSize, $margin + $shineH, $margin, $margin + $shineH)
$shinePath.CloseFigure()

# Clip to circle
$g.SetClip($circlePath)
$shineBrush = New-Object System.Drawing.Drawing2D.LinearGradientBrush(
    (New-Object System.Drawing.Rectangle($margin, $margin, $circleSize, $shineH)),
    [System.Drawing.Color]::FromArgb(120, 255, 255, 255),
    [System.Drawing.Color]::FromArgb(15, 255, 255, 255),
    [System.Drawing.Drawing2D.LinearGradientMode]::Vertical
)
$g.FillPath($shineBrush, $shinePath)
$shineBrush.Dispose()
$shinePath.Dispose()
$g.ResetClip()

# Subtle border
$borderPen = New-Object System.Drawing.Pen([System.Drawing.Color]::FromArgb(60, 0, 0, 0), 1.5)
$g.DrawPath($borderPen, $circlePath)
$borderPen.Dispose()
$circlePath.Dispose()

# === QUESTION MARK (white, bold) ===
$font = New-Object System.Drawing.Font("Segoe UI", 58, [System.Drawing.FontStyle]::Bold)
$textBrush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::White)
$sf = New-Object System.Drawing.StringFormat
$sf.Alignment = [System.Drawing.StringAlignment]::Center
$sf.LineAlignment = [System.Drawing.StringAlignment]::Center

# Slight shadow for depth
$shadowBrush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(50, 0, 0, 0))
$shadowRect = New-Object System.Drawing.RectangleF(2, 4, $size, $size)
$g.DrawString("?", $font, $shadowBrush, $shadowRect, $sf)
$shadowBrush.Dispose()

# White question mark
$textRect = New-Object System.Drawing.RectangleF(0, 0, $size, $size)
$g.DrawString("?", $font, $textBrush, $textRect, $sf)

$font.Dispose()
$textBrush.Dispose()
$sf.Dispose()
$g.Dispose()

$outPath = 'C:\Users\quinson\Desktop\Claude\Tableau DWH\twbx_help\Image\HelpIcon.png'
$bmp.Save($outPath, [System.Drawing.Imaging.ImageFormat]::Png)
$bmp.Dispose()
Write-Host "Created: HelpIcon.png ($size x $size)"
