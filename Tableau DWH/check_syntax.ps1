$tokens = $null
$errors = $null
[System.Management.Automation.Language.Parser]::ParseFile(
    'C:\Users\quinson\Desktop\Claude\MAJ Dashboard DWH\TransfertInventaire.ps1',
    [ref]$tokens, [ref]$errors
) | Out-Null
if ($errors -and $errors.Count -gt 0) {
    Write-Host "Syntax ERRORS:" -ForegroundColor Red
    $errors | ForEach-Object { Write-Host "  Line $($_.Extent.StartLineNumber): $($_.Message)" }
} else {
    Write-Host "Syntax OK" -ForegroundColor Green
}
