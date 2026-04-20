Add-Type -AssemblyName System.Drawing

# Zone dimensions in Tableau coords: w=33778, h=6182 out of 100000
# Dashboard is 1800x1100 px
# Image width = 33778/100000 * 1800 = 608 px
# Image height = 6182/100000 * 1100 = 68 px
$width = 608
$height = 68
$cornerRadius = 16
$bgColor = [System.Drawing.Color]::FromArgb(230, 230, 230)  # #e6e6e6

$bmp = New-Object System.Drawing.Bitmap($width, $height, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
$g.Clear([System.Drawing.Color]::Transparent)

# Create rounded rectangle path
$path = New-Object System.Drawing.Drawing2D.GraphicsPath
$r = $cornerRadius
$rect = New-Object System.Drawing.Rectangle(0, 0, $width, $height)
$path.AddArc($rect.X, $rect.Y, $r * 2, $r * 2, 180, 90)
$path.AddArc($rect.Right - $r * 2, $rect.Y, $r * 2, $r * 2, 270, 90)
$path.AddArc($rect.Right - $r * 2, $rect.Bottom - $r * 2, $r * 2, $r * 2, 0, 90)
$path.AddArc($rect.X, $rect.Bottom - $r * 2, $r * 2, $r * 2, 90, 90)
$path.CloseFigure()

$brush = New-Object System.Drawing.SolidBrush($bgColor)
$g.FillPath($brush, $path)

$brush.Dispose()
$path.Dispose()
$g.Dispose()

# Save for Suivi Evolution
$outPath1 = 'C:\Users\quinson\Desktop\Claude\Tableau DWH\twbx_roundcorners\Image\Cadre Filtres Evo.png'
$bmp.Save($outPath1, [System.Drawing.Imaging.ImageFormat]::Png)
Write-Host "Created: $outPath1 ($width x $height)"

# Also create one for Suivi Evolution Statuts (different width: w=20111)
$width2 = [int](20111.0 / 100000 * 1800)  # 362 px
$bmp2 = New-Object System.Drawing.Bitmap($width2, $height, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
$g2 = [System.Drawing.Graphics]::FromImage($bmp2)
$g2.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
$g2.Clear([System.Drawing.Color]::Transparent)

$path2 = New-Object System.Drawing.Drawing2D.GraphicsPath
$rect2 = New-Object System.Drawing.Rectangle(0, 0, $width2, $height)
$path2.AddArc($rect2.X, $rect2.Y, $r * 2, $r * 2, 180, 90)
$path2.AddArc($rect2.Right - $r * 2, $rect2.Y, $r * 2, $r * 2, 270, 90)
$path2.AddArc($rect2.Right - $r * 2, $rect2.Bottom - $r * 2, $r * 2, $r * 2, 0, 90)
$path2.AddArc($rect2.X, $rect2.Bottom - $r * 2, $r * 2, $r * 2, 90, 90)
$path2.CloseFigure()

$brush2 = New-Object System.Drawing.SolidBrush($bgColor)
$g2.FillPath($brush2, $path2)

$brush2.Dispose()
$path2.Dispose()
$g2.Dispose()

$outPath2 = 'C:\Users\quinson\Desktop\Claude\Tableau DWH\twbx_roundcorners\Image\Cadre Filtres Statuts.png'
$bmp2.Save($outPath2, [System.Drawing.Imaging.ImageFormat]::Png)
Write-Host "Created: $outPath2 ($width2 x $height)"

$bmp.Dispose()
$bmp2.Dispose()
