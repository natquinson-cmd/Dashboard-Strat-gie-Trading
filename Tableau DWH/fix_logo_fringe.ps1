Add-Type -AssemblyName System.Drawing

$origPath = "C:\Users\quinson\Desktop\Claude\Tableau DWH\twbx_extracted\Image\Logo EPFL - ORIGINAL.png"
$outPath  = "C:\Users\quinson\Desktop\Claude\Tableau DWH\twbx_extracted\Image\Logo EPFL.png"

# Load original (8bpp indexed, white background, red text)
$orig = New-Object System.Drawing.Bitmap($origPath)

# Create new 32bpp ARGB image
$img = New-Object System.Drawing.Bitmap($orig.Width, $orig.Height, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
$g = [System.Drawing.Graphics]::FromImage($img)
$g.DrawImage($orig, 0, 0, $orig.Width, $orig.Height)
$g.Dispose()
$orig.Dispose()

$fixed = 0
for ($y = 0; $y -lt $img.Height; $y++) {
    for ($x = 0; $x -lt $img.Width; $x++) {
        $p = $img.GetPixel($x, $y)
        $r = [int]$p.R; $g2 = [int]$p.G; $b = [int]$p.B

        # Pure white → fully transparent
        if ($r -ge 252 -and $g2 -ge 252 -and $b -ge 252) {
            $img.SetPixel($x, $y, [System.Drawing.Color]::FromArgb(0, 0, 0, 0))
            $fixed++
            continue
        }

        # Pure red (or very close) → keep fully opaque
        if ($r -ge 200 -and $g2 -le 15 -and $b -le 15) {
            # Already good, keep as-is
            continue
        }

        # Anti-aliased edge pixels: R is high, G/B are elevated from white blending
        # Original formula: displayed = foreground * alpha + white * (1-alpha)
        # For red (255,0,0) on white (255,255,255):
        #   displayed_G = 0*a + 255*(1-a) = 255*(1-a)  => a = 1 - displayed_G/255
        #   displayed_B = same
        # Use min(G,B) for more robust alpha estimation
        if ($r -gt 100) {
            $minGB = [Math]::Min($g2, $b)
            $newAlpha = [int][Math]::Round(255 - $minGB)
            $newAlpha = [Math]::Max(0, [Math]::Min(255, $newAlpha))

            if ($newAlpha -lt 8) {
                $img.SetPixel($x, $y, [System.Drawing.Color]::FromArgb(0, 0, 0, 0))
            } else {
                # Reconstruct original red color
                # For the R channel: displayed_R = origR * a + 255*(1-a)
                # origR = (displayed_R - 255*(1-a)) / a
                $a = $newAlpha / 255.0
                $origR = [int][Math]::Round(($r - 255 * (1 - $a)) / $a)
                $origR = [Math]::Max(0, [Math]::Min(255, $origR))
                $img.SetPixel($x, $y, [System.Drawing.Color]::FromArgb($newAlpha, $origR, 0, 0))
            }
            $fixed++
        }
    }
}

$img.Save($outPath, [System.Drawing.Imaging.ImageFormat]::Png)
$img.Dispose()
Write-Host "Fixed $fixed pixels. Logo saved to $outPath"
