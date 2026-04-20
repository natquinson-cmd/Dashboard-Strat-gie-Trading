Add-Type -AssemblyName System.IO.Compression.FileSystem

$twbxPath = 'C:\Users\quinson\Desktop\Claude\Dasboard suivi projet DataWarehouse.twbx'
$tempDir = 'C:\Users\quinson\Desktop\Claude\Tableau DWH\twbx_count'
if (Test-Path $tempDir) { Remove-Item $tempDir -Recurse -Force }

# Re-extract from original - need user to recopy first, but let's check current state
# Actually the repackaged file has wrong XML. Let me just show what needs to happen.
# User needs to recopy. For now let me show the original structure from the first extraction.

# The original zone block was:
# Line N+0: <zone h='6182' id='1102' type-v2='empty' w='33778' x='18278' y='8273'>
# Line N+1:   <zone-style>
# Line N+2:     <format attr='border-color' value='#000000' />
# Line N+3:     <format attr='border-style' value='none' />
# Line N+4:     <format attr='border-width' value='0' />
# Line N+5:     <format attr='background-color' value='#e6e6e6' />
# Line N+6:   </zone-style>
# Line N+7: </zone>

# That's 8 lines total (0-7), so skip = 7 (skip lines 1 through 7 after the opening tag)
Write-Host "The zone block is 8 lines. Need skip = 7, not 6."
