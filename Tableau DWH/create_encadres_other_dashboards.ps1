Add-Type -AssemblyName System.Drawing

$imageFolder = "C:\Users\quinson\Desktop\Claude\Tableau DWH\twbx_extracted\Image"

# Same style as Suivi Global encadres (thin border, button-style)
$cardColor    = [System.Drawing.Color]::FromArgb(255, 15, 23, 42)    # #0f172a
$borderIndigo = [System.Drawing.Color]::FromArgb(180, 99, 102, 241)  # #6366f1
$glowSubtle   = [System.Drawing.Color]::FromArgb(35, 99, 102, 241)
$shadowColor  = [System.Drawing.Color]::FromArgb(80, 0, 0, 0)

$fileSpecs = @(
    # Suivi Evolution
    @{ Name = "Encadre Evo Burnup.png";       W = 1800; H = 330 },
    @{ Name = "Encadre Evo Statut.png";       W = 1800; H = 292 },
    @{ Name = "Encadre Evo Workload.png";     W = 1800; H = 401 },
    # Suivi Evolution Statuts (one image reused 4 times)
    @{ Name = "Encadre EvoStatut Section.png"; W = 1800; H = 242 },
    # Suivi Retard
    @{ Name = "Encadre Retard KPI.png";       W = 720;  H = 248 },
    @{ Name = "Encadre Retard List.png";      W = 1058; H = 281 },
    @{ Name = "Encadre Retard Evolution.png"; W = 1800; H = 418 },
    @{ Name = "Encadre Retard Nouveaux.png";  W = 1800; H = 303 }
)

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

foreach ($spec in $fileSpecs) {
    $filePath = Join-Path $imageFolder $spec.Name
    $w = $spec.W
    $h = $spec.H

    $bmp = New-Object System.Drawing.Bitmap($w, $h)
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $g.Clear([System.Drawing.Color]::Transparent)

    $cornerRadius = 12
    $margin = 4

    # Shadow layer (offset 2px down)
    $shadowPath = New-RoundedRectPath -x ($margin) -y ($margin + 2) -w ($w - $margin * 2) -h ($h - $margin * 2) -r $cornerRadius
    $shadowBrush = New-Object System.Drawing.SolidBrush($shadowColor)
    $g.FillPath($shadowBrush, $shadowPath)
    $shadowBrush.Dispose()
    $shadowPath.Dispose()

    # Subtle glow layer (2px expansion)
    $glowPath = New-RoundedRectPath -x ($margin - 2) -y ($margin - 2) -w ($w - $margin * 2 + 4) -h ($h - $margin * 2 + 4) -r ($cornerRadius + 2)
    $glowBrush = New-Object System.Drawing.SolidBrush($glowSubtle)
    $g.FillPath($glowBrush, $glowPath)
    $glowBrush.Dispose()
    $glowPath.Dispose()

    # Main card fill
    $cardPath = New-RoundedRectPath -x $margin -y $margin -w ($w - $margin * 2) -h ($h - $margin * 2) -r $cornerRadius
    $cardBrush = New-Object System.Drawing.SolidBrush($cardColor)
    $g.FillPath($cardBrush, $cardPath)
    $cardBrush.Dispose()

    # Border (1.5px)
    $borderPen = New-Object System.Drawing.Pen($borderIndigo, 1.5)
    $g.DrawPath($borderPen, $cardPath)
    $borderPen.Dispose()
    $cardPath.Dispose()

    $g.Dispose()
    $bmp.Save($filePath, [System.Drawing.Imaging.ImageFormat]::Png)
    $bmp.Dispose()

    Write-Host "Created: $($spec.Name) ($w x $h)"
}

Write-Host "`nAll 8 encadre images generated successfully."
