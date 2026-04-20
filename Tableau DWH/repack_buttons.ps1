Add-Type -AssemblyName System.IO.Compression.FileSystem

$tempDir = 'C:\Users\quinson\Desktop\Claude\Tableau DWH\twbx_buttons'
$twbxPath = 'C:\Users\quinson\Desktop\Claude\Dasboard suivi projet DataWarehouse.twbx'

$tempZip = "$tempDir.zip"
if (Test-Path $tempZip) { Remove-Item $tempZip -Force }
[System.IO.Compression.ZipFile]::CreateFromDirectory($tempDir, $tempZip)
Copy-Item $tempZip $twbxPath -Force
Remove-Item $tempZip -Force
Remove-Item $tempDir -Recurse -Force

Write-Host "TWBX repackaged: $twbxPath"
