Add-Type -AssemblyName System.Drawing

$outPath = "C:\Users\quinson\Desktop\Claude\Tableau DWH\KPI_Box_Glossy.png"

# Same size as original: 300x300
$size = 300
$bmp = New-Object System.Drawing.Bitmap($size, $size)
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
$g.Clear([System.Drawing.Color]::Transparent)

# Geometry
$padding = 25
$shadowOffset = 5
$cornerRadius = 20

function New-RoundedRectPath {
    param([float]$x, [float]$y, [float]$w, [float]$h, [float]$r)
    $path = New-Object System.Drawing.Drawing2D.GraphicsPath
    $d = $r * 2
    if ($d -gt $h) { $d = $h }
    if ($d -gt $w) { $d = $w }
    $path.AddArc($x, $y, $d, $d, 180, 90)
    $path.AddArc($x + $w - $d, $y, $d, $d, 270, 90)
    $path.AddArc($x + $w - $d, $y + $h - $d, $d, $d, 0, 90)
    $path.AddArc($x, $y + $h - $d, $d, $d, 90, 90)
    $path.CloseFigure()
    return $path
}

[float]$rx = $padding
[float]$ry = $padding
[float]$rw = $size - $padding * 2 - $shadowOffset
[float]$rh = $size - $padding * 2 - $shadowOffset

# 1. Shadow (black, offset, layered for softness)
for ($i = 4; $i -ge 0; $i--) {
    [int]$alpha = 15 + ($i * 10)
    $sp = New-RoundedRectPath ($rx + $shadowOffset + $i) ($ry + $shadowOffset + $i) $rw $rh $cornerRadius
    $sb = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb($alpha, 0, 0, 0))
    $g.FillPath($sb, $sp)
    $sb.Dispose(); $sp.Dispose()
}

# 2. Outer glow (indigo subtle)
$glowPath = New-RoundedRectPath ($rx - 1) ($ry - 1) ($rw + 2) ($rh + 2) ($cornerRadius + 1)
$glowBrush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(35, 99, 102, 241))
$g.FillPath($glowBrush, $glowPath)
$glowBrush.Dispose(); $glowPath.Dispose()

# 3. Card fill - SAME as encadres: #0f172a (opaque)
$cardPath = New-RoundedRectPath $rx $ry $rw $rh $cornerRadius
$cardBrush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(255, 15, 23, 42))
$g.FillPath($cardBrush, $cardPath)
$cardBrush.Dispose()

# 4. Glossy highlight on top 45%
$clipState = $g.Save()
$g.SetClip($cardPath)
[float]$glossyBottom = $ry + ($rh * 0.45)
$pt1 = New-Object System.Drawing.PointF($rx, $ry)
$pt2 = New-Object System.Drawing.PointF($rx, $glossyBottom)
$glossyRect = New-Object System.Drawing.RectangleF($rx, $ry, $rw, ($rh * 0.45))
$glossyBrush = New-Object System.Drawing.Drawing2D.LinearGradientBrush(
    $pt1, $pt2,
    [System.Drawing.Color]::FromArgb(45, 180, 200, 255),
    [System.Drawing.Color]::FromArgb(0, 180, 200, 255)
)
$g.FillRectangle($glossyBrush, $glossyRect)
$glossyBrush.Dispose()
$g.Restore($clipState)

# 5. Inner highlight at top edge
$clipState2 = $g.Save()
[float]$topClipH = $rh * 0.15
$topClip = New-Object System.Drawing.RectangleF($rx, $ry, $rw, $topClipH)
$g.SetClip($topClip)
$innerPath = New-RoundedRectPath ($rx + 1.5) ($ry + 1.5) ($rw - 3) ($rh - 3) ($cornerRadius - 1.5)
$innerPen = New-Object System.Drawing.Pen([System.Drawing.Color]::FromArgb(40, 200, 220, 255), 1.5)
$g.DrawPath($innerPen, $innerPath)
$innerPen.Dispose(); $innerPath.Dispose()
$g.Restore($clipState2)

# 6. Border indigo (same as encadres)
$borderPen = New-Object System.Drawing.Pen([System.Drawing.Color]::FromArgb(180, 99, 102, 241), 2)
$g.DrawPath($borderPen, $cardPath)
$borderPen.Dispose()
$cardPath.Dispose()

$g.Dispose()
$bmp.Save($outPath, [System.Drawing.Imaging.ImageFormat]::Png)
$bmp.Dispose()

# Verify
$verify = [System.Drawing.Image]::FromFile($outPath)
Write-Host "Created: $($verify.Width) x $($verify.Height)"
$verify.Dispose()

# Encode to base64 and inject into TWB
$bytes = [System.IO.File]::ReadAllBytes($outPath)
$b64 = [Convert]::ToBase64String($bytes)
Write-Host "Base64 length: $($b64.Length)"

$twbPath = "C:\Users\quinson\Desktop\Claude\Tableau DWH\twbx_extracted\Dasboard DataWarehouse V4.twb"
[xml]$doc = [System.IO.File]::ReadAllText($twbPath, [System.Text.Encoding]::UTF8)

foreach ($s in $doc.workbook.external.shapes.shape) {
    if ($s.name -eq "My shapes/KPI Box - Shadow.png") {
        $s.InnerText = $b64
        Write-Host "Shape data replaced in XML"
        break
    }
}

# Save with proper indentation
$settings = New-Object System.Xml.XmlWriterSettings
$settings.Indent = $true
$settings.IndentChars = "  "
$settings.Encoding = New-Object System.Text.UTF8Encoding($false)
$settings.NewLineHandling = [System.Xml.NewLineHandling]::Replace
$settings.NewLineChars = "`n"

$writer = [System.Xml.XmlWriter]::Create($twbPath, $settings)
$doc.Save($writer)
$writer.Close()

$lines = [System.IO.File]::ReadAllLines($twbPath).Length
Write-Host "TWB saved: $lines lines"

try {
    [xml]$v = [System.IO.File]::ReadAllText($twbPath, [System.Text.Encoding]::UTF8)
    Write-Host "XML: OK"
} catch {
    Write-Host "XML: ERREUR"
}

(Get-Item $twbPath).LastWriteTime = Get-Date
Write-Host "Done!"
