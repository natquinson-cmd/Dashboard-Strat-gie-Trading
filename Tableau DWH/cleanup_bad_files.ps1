$imageFolder = "C:\Users\quinson\Desktop\Claude\Tableau DWH\twbx_extracted\Image"

# Get all Encadr* files
$allFiles = [System.IO.Directory]::GetFiles($imageFolder, "Encadr*")

# The correct files use char U+00E9 (é = single Unicode codepoint)
# Bad files use other encodings like +® or Ǹ (multi-byte corruptions)

$goodChar = [char]0x00E9  # é

foreach ($f in $allFiles) {
    $name = [System.IO.Path]::GetFileName($f)
    if ($name.Contains($goodChar)) {
        Write-Host "KEEP: $name"
    } else {
        Remove-Item -LiteralPath $f -Force
        Write-Host "DELETED: $name"
    }
}

Write-Host ""
Write-Host "=== Remaining files ==="
[System.IO.Directory]::GetFiles($imageFolder, "Encadr*") | ForEach-Object {
    $fi = [System.IO.FileInfo]::new($_)
    Write-Host "  $($fi.Name)  ($($fi.Length) bytes)"
}
