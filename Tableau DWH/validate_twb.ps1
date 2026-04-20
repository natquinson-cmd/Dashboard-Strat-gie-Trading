$f = "C:\Users\quinson\Desktop\Claude\Tableau DWH\twbx_extracted\Dasboard DataWarehouse V4.twb"
try {
    [xml]$doc = [System.IO.File]::ReadAllText($f, [System.Text.Encoding]::UTF8)
    Write-Host "XML: OK"
} catch {
    Write-Host "XML: ERREUR - $($_.Exception.Message)"
}
(Get-Item $f).LastWriteTime = Get-Date
Write-Host "TWB updated: $((Get-Item $f).LastWriteTime)"
