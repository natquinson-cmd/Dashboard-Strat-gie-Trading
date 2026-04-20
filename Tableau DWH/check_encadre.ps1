Add-Type -AssemblyName System.Drawing
$folder = "C:\Users\quinson\Desktop\Claude\Tableau DWH\twbx_extracted\Image"
Get-ChildItem "$folder\Encadr*" | ForEach-Object {
    $img = [System.Drawing.Image]::FromFile($_.FullName)
    Write-Host "$($_.Name) : $($img.Width)x$($img.Height) Format=$($img.PixelFormat)"
    $img.Dispose()
}
