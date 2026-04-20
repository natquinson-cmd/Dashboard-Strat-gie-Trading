Add-Type -AssemblyName System.Drawing
$imgDir = 'C:\Users\quinson\Desktop\Claude\Tableau DWH\twbx_extracted\Image'
foreach ($n in @('Bouton gauche.png','Bouton milieu.png','Bouton droit.png','Bouton seul.png')) {
    $p = Join-Path $imgDir $n
    $img = [System.Drawing.Image]::FromFile($p)
    Write-Host "$n : $($img.Width) x $($img.Height)"
    $img.Dispose()
}
