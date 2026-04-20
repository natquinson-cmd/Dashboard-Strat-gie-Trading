Add-Type -AssemblyName System.Drawing

$f = "C:\Users\quinson\Desktop\Claude\Tableau DWH\twbx_extracted\Dasboard DataWarehouse V4.twb"
$c = [System.IO.File]::ReadAllText($f, [System.Text.Encoding]::UTF8)

$imgPath = "C:\Users\quinson\Desktop\Claude\Tableau DWH\twbx_extracted\Image"
$prefix = "C:/Users/quinson/Desktop/Claude/Tableau DWH/twbx_extracted/Image"

# Helper to build old/new zone strings
function Update-Zone {
    param($content, $id, $img, $oh, $ow, $ox, $oy, $nh, $nw, $nx, $ny)
    # Desktop version (ends with />)
    $old = "h='$oh' id='$id' is-centered='0' is-scaled='1' param='$prefix/$img' type-v2='bitmap' w='$ow' x='$ox' y='$oy' />"
    $new = "h='$nh' id='$id' is-centered='0' is-scaled='1' param='$prefix/$img' type-v2='bitmap' w='$nw' x='$nx' y='$ny' />"
    $content = $content.Replace($old, $new)
    # Phone version (ends with >)
    $old2 = "h='$oh' id='$id' is-centered='0' is-fixed='true' is-scaled='1' param='$prefix/$img' type-v2='bitmap' w='$ow' x='$ox' y='$oy'>"
    $new2 = "h='$nh' id='$id' is-centered='0' is-fixed='true' is-scaled='1' param='$prefix/$img' type-v2='bitmap' w='$nw' x='$nx' y='$ny'>"
    $content = $content.Replace($old2, $new2)
    return $content
}

# === SUIVI EVOLUTION ===
$c = Update-Zone $c "2001" "Encadre Evo Burnup.png"   30000 100000 500 7800  29302 99444 278 7800
$c = Update-Zone $c "2002" "Encadre Evo Statut.png"    26500 100000 500 37000 25876 99444 278 37557
$c = Update-Zone $c "2003" "Encadre Evo Workload.png"  36500 100000 500 62500 35657 99444 278 63888

# === SUIVI EVOLUTION STATUTS ===
$c = Update-Zone $c "2004" "Encadre EvoStatut Section.png" 22000 100000 0 15000 20795 99444 278 15000
$c = Update-Zone $c "2005" "Encadre EvoStatut Section.png" 22000 100000 0 36000 20795 99444 278 36250
$c = Update-Zone $c "2006" "Encadre EvoStatut Section.png" 22000 100000 0 57000 20795 99444 278 57500
$c = Update-Zone $c "2007" "Encadre EvoStatut Section.png" 22000 100000 0 78000 20795 99444 278 78750

# === SUIVI RETARD ===
$c = Update-Zone $c "2008" "Encadre Retard KPI.png"       23000 40000  500   10500 25054 40148 278   10455
$c = Update-Zone $c "2009" "Encadre Retard List.png"       26000 58800  40700 9500  25054 59018 40704 10455
$c = Update-Zone $c "2010" "Encadre Retard Evolution.png"  38000 100000 0     34500 36636 99444 278   35964
$c = Update-Zone $c "2011" "Encadre Retard Nouveaux.png"   27500 100000 0     72000 26490 99444 278   73055

[System.IO.File]::WriteAllText($f, $c, [System.Text.Encoding]::UTF8)

# Validate XML
try {
    [xml]$doc = [System.IO.File]::ReadAllText($f, [System.Text.Encoding]::UTF8)
    Write-Host "XML: OK"
} catch {
    Write-Host "XML: ERREUR - $($_.Exception.Message)"
}
(Get-Item $f).LastWriteTime = Get-Date
Write-Host "TWB updated: $((Get-Item $f).LastWriteTime)"

# === GENERATE ALL ENCADRE IMAGES ===
$cardColor    = [System.Drawing.Color]::FromArgb(255, 15, 23, 42)    # #0f172a
$borderIndigo = [System.Drawing.Color]::FromArgb(180, 99, 102, 241)  # #6366f1
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
    Write-Host "  $name ($w x $h)"
}

Write-Host "`n=== Generating images ==="
# Suivi Evolution
New-EncadreImage "Encadre Evo Burnup.png"   1790 322
New-EncadreImage "Encadre Evo Statut.png"    1790 285
New-EncadreImage "Encadre Evo Workload.png"  1790 392

# Suivi Evolution Statuts (1 image, 4 zones)
New-EncadreImage "Encadre EvoStatut Section.png" 1790 229

# Suivi Retard
New-EncadreImage "Encadre Retard KPI.png"       723  276
New-EncadreImage "Encadre Retard List.png"       1062 276
New-EncadreImage "Encadre Retard Evolution.png"  1790 403
New-EncadreImage "Encadre Retard Nouveaux.png"   1790 291

Write-Host "`nAll done!"
