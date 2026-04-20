$imageFolder = "C:\Users\quinson\Desktop\Claude\Tableau DWH\twbx_extracted\Image"

# Find all files with corrupted "Encadr" names (not ORIGINAL backups)
$corruptedFiles = Get-ChildItem "$imageFolder\Encadr*Page1.png" | Where-Object { $_.Name -notmatch 'ORIGINAL' }

Write-Host "Found $($corruptedFiles.Count) encadre files to check:"

foreach ($f in $corruptedFiles) {
    $oldName = $f.Name
    $oldPath = $f.FullName

    # Check if filename already contains proper e-acute
    if ($oldName -match 'Encadré') {
        Write-Host "  ALREADY OK: $oldName"
        continue
    }

    # Build the correct name with proper e-acute
    # Replace everything between "Encadr" and the rest with proper e-acute
    $newName = $oldName -replace '^Encadr[^\s]+\s', 'Encadré '

    # If that didn't work, try another pattern
    if ($newName -eq $oldName) {
        # Manual mapping based on what we know
        if ($oldName -match 'Haut Gauche') { $newName = "Encadré Haut Gauche Page1.png" }
        elseif ($oldName -match 'Haut Droite') { $newName = "Encadré Haut Droite Page1.png" }
        elseif ($oldName -match 'Haut Milieu') { $newName = "Encadré Haut Milieu Page1.png" }
        elseif ($oldName -match 'bas gauche') { $newName = "Encadré bas gauche Page1.png" }
        elseif ($oldName -match 'bas droite') { $newName = "Encadré bas droite Page1.png" }
        elseif ($oldName -match 'milieu Page') { $newName = "Encadré milieu Page 1.png" }
        else {
            Write-Host "  SKIP (unknown pattern): $oldName"
            continue
        }
    }

    $newPath = Join-Path $imageFolder $newName

    if ($oldPath -ne $newPath) {
        # Copy with correct name (don't move, in case source has weird encoding)
        Copy-Item $oldPath $newPath -Force
        Write-Host "  RENAMED: $oldName -> $newName"

        # Remove old corrupted file
        Remove-Item $oldPath -Force
        Write-Host "  REMOVED old: $oldName"
    } else {
        Write-Host "  SAME PATH: $oldName"
    }
}

# Verify final state
Write-Host ""
Write-Host "=== Final Image folder contents ==="
Get-ChildItem "$imageFolder\Encadr*" | ForEach-Object {
    Write-Host "  $($_.Name) ($($_.Length) bytes)"
}

# Also verify TWB references match
Write-Host ""
Write-Host "=== TWB references ==="
$twbPath = "C:\Users\quinson\Desktop\Claude\Tableau DWH\twbx_extracted\Dasboard DataWarehouse V4.twb"
$content = Get-Content $twbPath -Encoding UTF8 -Raw
$matches = [regex]::Matches($content, "param='Image/(Encadr[^']+)'")
foreach ($m in $matches) {
    $refName = $m.Groups[1].Value
    $filePath = Join-Path $imageFolder $refName
    $exists = Test-Path $filePath
    $status = if ($exists) { "OK" } else { "MISSING!" }
    Write-Host "  [$status] $refName"
}
