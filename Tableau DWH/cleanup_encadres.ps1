$imageFolder = "C:\Users\quinson\Desktop\Claude\Tableau DWH\twbx_extracted\Image"
Get-ChildItem "$imageFolder\Encadr*" | ForEach-Object {
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($_.Name)
    $hasWeirdChar = $_.Name.Contains([char]0x01F8) -or $_.Name.Contains([char]0x0178)
    if ($hasWeirdChar) {
        Remove-Item $_.FullName -Force
        Write-Host "Removed bad encoding: $($_.Name)"
    } else {
        Write-Host "OK: $($_.Name) ($($_.Length) bytes)"
    }
}
