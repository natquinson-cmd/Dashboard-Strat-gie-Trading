$twbPath = "C:\Users\quinson\Desktop\Claude\Tableau DWH\twbx_extracted\Dasboard DataWarehouse V4.twb"

# Read as raw bytes
$bytes = [System.IO.File]::ReadAllBytes($twbPath)
Write-Host "File size: $($bytes.Length) bytes"

# Search for "Encadr" in the bytes
$searchBytes = [System.Text.Encoding]::UTF8.GetBytes("Encadr")
$searchLen = $searchBytes.Length

for ($i = 0; $i -lt $bytes.Length - $searchLen; $i++) {
    $match = $true
    for ($j = 0; $j -lt $searchLen; $j++) {
        if ($bytes[$i + $j] -ne $searchBytes[$j]) {
            $match = $false
            break
        }
    }
    if ($match) {
        # Found "Encadr" at position $i, read next 60 bytes
        $contextLen = [Math]::Min(60, $bytes.Length - $i)
        $contextBytes = $bytes[$i..($i + $contextLen - 1)]
        $hexStr = ($contextBytes | ForEach-Object { $_.ToString("X2") }) -join " "

        # Try to decode as UTF-8
        $utf8Str = [System.Text.Encoding]::UTF8.GetString($contextBytes)

        Write-Host ""
        Write-Host "Found at byte $i :"
        Write-Host "  Hex: $hexStr"
        Write-Host "  UTF8: $utf8Str"

        # Show the specific byte after "Encadr" (should be e-acute)
        $accentByte = $bytes[$i + 6]
        Write-Host "  Byte after 'Encadr': 0x$($accentByte.ToString('X2')) (decimal: $accentByte)"
        if ($accentByte -eq 0xC3) {
            $nextByte = $bytes[$i + 7]
            Write-Host "  Next byte: 0x$($nextByte.ToString('X2')) -> UTF-8 e-acute = C3 A9"
        }
        elseif ($accentByte -eq 0xE9) {
            Write-Host "  -> This is Latin-1 e-acute (0xE9)"
        }
    }
}
