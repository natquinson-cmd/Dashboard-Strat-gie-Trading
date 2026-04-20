$twbPath = "C:\Users\quinson\Desktop\Claude\Tableau DWH\twbx_extracted\Dasboard DataWarehouse V4.twb"

# Load and re-save with proper indentation
[xml]$doc = [System.IO.File]::ReadAllText($twbPath, [System.Text.Encoding]::UTF8)

$settings = New-Object System.Xml.XmlWriterSettings
$settings.Indent = $true
$settings.IndentChars = "  "
$settings.Encoding = New-Object System.Text.UTF8Encoding($false)
$settings.NewLineHandling = [System.Xml.NewLineHandling]::Replace
$settings.NewLineChars = "`n"
$settings.OmitXmlDeclaration = $false

$writer = [System.Xml.XmlWriter]::Create($twbPath, $settings)
$doc.Save($writer)
$writer.Close()

# Count lines
$lines = [System.IO.File]::ReadAllLines($twbPath).Length
Write-Host "TWB reformatted: $lines lines"

# Validate
try {
    [xml]$verify = [System.IO.File]::ReadAllText($twbPath, [System.Text.Encoding]::UTF8)
    Write-Host "XML validation: OK"
} catch {
    Write-Host "XML validation: ERROR - $($_.Exception.Message)"
}
