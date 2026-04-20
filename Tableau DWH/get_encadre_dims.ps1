Add-Type -AssemblyName System.Drawing
$imgPath = "C:\Users\quinson\Desktop\Claude\Tableau DWH\twbx_extracted\Image"
Get-ChildItem "$imgPath\Encadre*" | ForEach-Object {
    $img = [System.Drawing.Image]::FromFile($_.FullName)
    Write-Host "$($_.Name) : $($img.Width) x $($img.Height)"
    $img.Dispose()
}
