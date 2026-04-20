$imageFolder = "C:\Users\quinson\Desktop\Claude\Tableau DWH\twbx_extracted\Image"

# Rename files: Encadré -> Encadre (remove accent)
$goodChar = [char]0x00E9  # é
$files = [System.IO.Directory]::GetFiles($imageFolder, "Encadr*")

foreach ($f in $files) {
    $name = [System.IO.Path]::GetFileName($f)
    $newName = $name.Replace($goodChar, 'e')
    if ($newName -ne $name) {
        $newPath = [System.IO.Path]::Combine($imageFolder, $newName)
        [System.IO.File]::Move($f, $newPath)
        Write-Host "Renamed: $name -> $newName"
    }
}

Write-Host ""
Write-Host "=== Files after rename ==="
[System.IO.Directory]::GetFiles($imageFolder, "Encadr*") | ForEach-Object {
    Write-Host "  $([System.IO.Path]::GetFileName($_))"
}
