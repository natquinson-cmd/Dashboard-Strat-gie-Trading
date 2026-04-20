$twbPath = "C:\Users\quinson\Desktop\Claude\Tableau DWH\twbx_extracted\Dasboard DataWarehouse V4.twb"
$b64Path = "C:\Users\quinson\Desktop\Claude\Tableau DWH\KPI_Box_Glossy_b64.txt"

# Read new base64 data
$newB64 = [System.IO.File]::ReadAllText($b64Path).Trim()
Write-Host "New base64 length: $($newB64.Length)"

# Parse TWB XML
[xml]$doc = [System.IO.File]::ReadAllText($twbPath, [System.Text.Encoding]::UTF8)

# Find and replace the shape data
$shapes = $doc.workbook.external.shapes.shape
$found = $false
foreach ($s in $shapes) {
    if ($s.name -eq "My shapes/KPI Box - Shadow.png") {
        $oldLen = $s.InnerText.Trim().Length
        $s.InnerText = $newB64
        Write-Host "Replaced shape data: $oldLen chars -> $($newB64.Length) chars"
        $found = $true
        break
    }
}

if (-not $found) {
    Write-Host "ERROR: Shape not found!"
    exit 1
}

# Save with UTF-8 encoding (no BOM to match original)
$settings = New-Object System.Xml.XmlWriterSettings
$settings.Indent = $false
$settings.Encoding = New-Object System.Text.UTF8Encoding($false)
$settings.NewLineHandling = [System.Xml.NewLineHandling]::None

$writer = [System.Xml.XmlWriter]::Create($twbPath, $settings)
$doc.Save($writer)
$writer.Close()
Write-Host "TWB saved."

# Validate
try {
    [xml]$verify = [System.IO.File]::ReadAllText($twbPath, [System.Text.Encoding]::UTF8)
    Write-Host "XML validation: OK"
} catch {
    Write-Host "XML validation: ERROR - $($_.Exception.Message)"
}
