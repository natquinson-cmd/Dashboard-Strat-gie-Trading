$filePath = "C:\Users\quinson\Downloads\WhatsApp Image 2026-04-08 at 09.23.03.jpeg"
$uploadUrl = "https://emilie-quinson.com/wp-content/uploads/2026/03/tmp-upload.php"
$newName = "emilie-fauteuil.jpg"

$boundary = [System.Guid]::NewGuid().ToString()
$LF = "`r`n"
$fileBytes = [System.IO.File]::ReadAllBytes($filePath)
$fileEnc = [System.Text.Encoding]::GetEncoding("iso-8859-1").GetString($fileBytes)

$bodyLines = (
    "--$boundary",
    "Content-Disposition: form-data; name=`"file`"; filename=`"$newName`"",
    "Content-Type: image/jpeg",
    "",
    $fileEnc,
    "--$boundary--"
) -join $LF

$response = Invoke-RestMethod -Uri $uploadUrl -Method Post -ContentType "multipart/form-data; boundary=$boundary" -Body $bodyLines
Write-Host $response
