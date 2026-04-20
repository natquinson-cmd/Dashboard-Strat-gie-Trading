Add-Type -AssemblyName System.Drawing

$twbPath = "C:\Users\quinson\Desktop\Claude\Tableau DWH\twbx_extracted\Dasboard DataWarehouse V4.twb"
$outPath = "C:\Users\quinson\Desktop\Claude\Tableau DWH\KPI_Box_Shadow_original.png"

# Parse XML and extract shape data
[xml]$doc = [System.IO.File]::ReadAllText($twbPath, [System.Text.Encoding]::UTF8)
$shapes = $doc.workbook.external.shapes.shape
foreach ($s in $shapes) {
    if ($s.name -eq "My shapes/KPI Box - Shadow.png") {
        $b64 = $s.InnerText.Trim()
        Write-Host "Found shape: $($s.name)"
        Write-Host "Base64 length: $($b64.Length)"

        # Decode and save
        $bytes = [Convert]::FromBase64String($b64)
        [System.IO.File]::WriteAllBytes($outPath, $bytes)
        Write-Host "Saved to: $outPath"

        # Get dimensions
        $img = [System.Drawing.Image]::FromFile($outPath)
        Write-Host "Dimensions: $($img.Width) x $($img.Height)"
        Write-Host "Pixel format: $($img.PixelFormat)"
        $img.Dispose()
        break
    }
}
