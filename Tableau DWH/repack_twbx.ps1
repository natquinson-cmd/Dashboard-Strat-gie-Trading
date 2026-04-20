$extractDir = 'C:\Users\quinson\Desktop\Claude\Tableau DWH\twbx_extracted'
$twbxPath = 'C:\Users\quinson\Desktop\Claude\Dasboard suivi projet DataWarehouse.twbx'
$tempZip = 'C:\Users\quinson\Desktop\Claude\Tableau DWH\temp_repack.zip'

# Remove old temp zip if exists
if (Test-Path $tempZip) { Remove-Item $tempZip -Force }

# Create ZIP from extracted directory
Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::CreateFromDirectory($extractDir, $tempZip)

# Replace the twbx
Copy-Item $tempZip $twbxPath -Force
Remove-Item $tempZip -Force

Write-Host "TWBX repackaged: $twbxPath"
Write-Host "Size: $((Get-Item $twbxPath).Length / 1MB) MB"
