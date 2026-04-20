try {
    [xml]$doc = Get-Content "C:\Users\quinson\Desktop\Claude\Tableau DWH\twbx_extracted\Dasboard DataWarehouse V4.twb" -Encoding UTF8
    Write-Host "XML valide!"
    Write-Host "Root: $($doc.DocumentElement.Name)"
    $dashboards = $doc.workbook.dashboards.dashboard
    foreach ($d in $dashboards) {
        $styleInfo = if ($d.style.InnerXml) { "has style" } else { "empty style" }
        Write-Host "  Dashboard: $($d.name) - $styleInfo"
    }
    Write-Host "Total worksheets: $($doc.workbook.worksheets.worksheet.Count)"
} catch {
    Write-Host "ERREUR XML: $_"
}
