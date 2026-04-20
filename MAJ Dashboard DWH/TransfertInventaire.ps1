#Requires -Version 5.1
<#
.SYNOPSIS
    Automatise le transfert du fichier "Inventaire de migration consolide.xlsx"
    depuis SharePoint EPFL vers le repertoire reseau.
.DESCRIPTION
    1. Ouvre le lien de telechargement SharePoint dans le navigateur (auth SSO)
    2. Attend que le fichier soit telecharge dans Downloads
    3. Archive l'ancien fichier dans Old (avec date de derniere modification)
    4. Copie le nouveau fichier dans le repertoire reseau
    Note: le nom du fichier utilise [char]0xE9 pour eviter les problemes
    d'encodage UTF-8 / ANSI avec PowerShell 5.1
#>

# ========================
# LOG : Tout est enregistre dans un fichier
# ========================
$LogFile = Join-Path $PSScriptRoot "TransfertInventaire_LOG.txt"
Start-Transcript -Path $LogFile -Force | Out-Null
Write-Host "=== LOG demarre : $LogFile ===" -ForegroundColor Gray
Write-Host "=== Date : $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ===" -ForegroundColor Gray

# ========================
# CONFIGURATION
# ========================
$DownloadUrl  = "https://epflch.sharepoint.com/sites/DataManagementProgram-DocumentationprojetDataWareHouseservices/_layouts/15/download.aspx?UniqueId=%7BC571B43F-CC46-4C4C-A3CA-AE83B6828DC4%7D"

# Construction du nom avec [char]0xE9 pour le e accent aigu
# Evite les problemes d'encodage UTF-8/ANSI de PowerShell 5.1
$FileName     = "Inventaire de migration consolid$([char]0xE9).xlsx"

$DownloadDir  = Join-Path $env:USERPROFILE "Downloads"
$DestDir      = "\\scxdata\CommunOS_BI$\C Courant\Datasources\ISCS-BI\SuiviProjetDWH\flatfiles"
$OldDir       = Join-Path $DestDir "Old"

$DownloadPath = Join-Path $DownloadDir $FileName
$DestPath     = Join-Path $DestDir $FileName

# Timeout en secondes pour attendre le telechargement
$DownloadTimeout = 120

Write-Host "`nConfiguration :" -ForegroundColor Gray
Write-Host "   Fichier     : $FileName" -ForegroundColor Gray
Write-Host "   Destination : $DestDir" -ForegroundColor Gray

# ========================
# FONCTIONS
# ========================
function Write-Step {
    param([string]$Message)
    Write-Host "`n>> $Message" -ForegroundColor Cyan
}

function Write-OK {
    param([string]$Message)
    Write-Host "   [OK] $Message" -ForegroundColor Green
}

function Write-Err {
    param([string]$Message)
    Write-Host "   [ERREUR] $Message" -ForegroundColor Red
}

function Exit-WithError {
    param([string]$Message)
    Write-Err $Message
    Write-Host "`n   >> Le log complet est dans : $LogFile" -ForegroundColor Yellow
    Stop-Transcript -ErrorAction SilentlyContinue | Out-Null
    Read-Host "`nAppuyez sur Entree pour quitter"
    exit 1
}

# ========================
# ETAPE 1 : Telechargement via le navigateur
# ========================
Write-Step "Preparation du telechargement..."

# Supprimer une eventuelle ancienne copie dans Downloads
if (Test-Path -LiteralPath $DownloadPath) {
    Remove-Item -LiteralPath $DownloadPath -Force
    Write-Host "   Ancienne copie dans Downloads supprimee." -ForegroundColor Gray
}

# Supprimer aussi les fichiers temporaires de telechargement precedent
Get-ChildItem $DownloadDir -Filter "Inventaire de migration consolid*.crdownload" -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue
Get-ChildItem $DownloadDir -Filter "Inventaire de migration consolid*.tmp" -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue

Write-Step "Ouverture du lien de telechargement dans le navigateur..."
Write-Host "   (votre session SSO EPFL sera utilisee automatiquement)" -ForegroundColor Gray
Start-Process $DownloadUrl

# Attendre que le fichier apparaisse dans Downloads
Write-Step "Attente du telechargement (max $DownloadTimeout sec)..."
$elapsed  = 0
$dotCount = 0
while (-not (Test-Path -LiteralPath $DownloadPath) -and $elapsed -lt $DownloadTimeout) {
    Start-Sleep -Seconds 3
    $elapsed += 3
    $dotCount++
    Write-Host "." -NoNewline
    if ($dotCount % 20 -eq 0) { Write-Host "" }
}
Write-Host ""

if (-not (Test-Path -LiteralPath $DownloadPath)) {
    # Verifier si le fichier a ete telecharge sous un autre nom (ex: avec un (1))
    $altFile = Get-ChildItem $DownloadDir -Filter "Inventaire de migration consolid*.xlsx" -ErrorAction SilentlyContinue |
               Where-Object { $_.Name -ne $FileName -and $_.LastWriteTime -gt (Get-Date).AddMinutes(-5) } |
               Sort-Object LastWriteTime -Descending |
               Select-Object -First 1

    if ($altFile) {
        Write-Host "   Fichier trouve sous un autre nom : $($altFile.Name)" -ForegroundColor Yellow
        $DownloadPath = $altFile.FullName
        Write-OK "Fichier detecte."
    }
    else {
        Exit-WithError "Le fichier n'a pas ete telecharge dans les $DownloadTimeout secondes.`n   Verifiez que vous etes connecte a votre compte EPFL dans le navigateur."
    }
}

# Attendre que le telechargement soit vraiment termine (taille stable)
Write-Host "   Verification de la fin du telechargement..." -ForegroundColor Gray
Start-Sleep -Seconds 2
$previousSize = -1
$currentSize  = (Get-Item -LiteralPath $DownloadPath).Length
$sizeChecks   = 0
while ($previousSize -ne $currentSize -and $sizeChecks -lt 30) {
    Start-Sleep -Seconds 2
    $previousSize = $currentSize
    $currentSize  = (Get-Item -LiteralPath $DownloadPath).Length
    $sizeChecks++
}

if ($currentSize -eq 0) {
    Exit-WithError "Le fichier telecharge est vide (0 octets). Verifiez le lien SharePoint."
}

$sizeMB = [math]::Round($currentSize / 1MB, 2)
Write-OK "Fichier telecharge : $DownloadPath ($sizeMB Mo)"

# ========================
# ETAPE 2 : Verifier acces reseau
# ========================
Write-Step "Verification de l'acces au repertoire reseau..."
if (-not (Test-Path -LiteralPath $DestDir)) {
    Exit-WithError "Le repertoire reseau est inaccessible : $DestDir`n   Verifiez que vous etes connecte au reseau / VPN."
}
Write-OK "Repertoire reseau accessible."

if (-not (Test-Path -LiteralPath $OldDir)) {
    Exit-WithError "Le sous-dossier Old est introuvable : $OldDir"
}
Write-OK "Sous-dossier Old accessible."

# ========================
# ETAPE 3 : Archiver l'ancien fichier dans Old
# ========================
Write-Step "Archivage de l'ancien fichier dans Old..."

if (Test-Path -LiteralPath $DestPath) {
    try {
        # Recuperer la date de derniere modification
        $lastModified = (Get-Item -LiteralPath $DestPath).LastWriteTime
        $dateStr      = $lastModified.ToString("dd.MM.yy")

        # Construire le nouveau nom
        $baseName     = [System.IO.Path]::GetFileNameWithoutExtension($FileName)
        $extension    = [System.IO.Path]::GetExtension($FileName)
        $archiveName  = "${baseName}_${dateStr}${extension}"
        $archivePath  = Join-Path $OldDir $archiveName

        Write-Host "   Date derniere modification : $($lastModified.ToString('dd/MM/yyyy HH:mm'))" -ForegroundColor Gray
        Write-Host "   Nom archive : $archiveName" -ForegroundColor Gray

        # Deplacer
        Move-Item -LiteralPath $DestPath -Destination $archivePath -Force
        Write-OK "Ancien fichier archive sous : $archiveName"
    }
    catch {
        Exit-WithError "Echec de l'archivage : $_"
    }
}
else {
    Write-Host "   Aucun fichier existant a archiver." -ForegroundColor Yellow
}

# ========================
# ETAPE 4 : Copier le nouveau fichier
# ========================
Write-Step "Copie du nouveau fichier vers le repertoire reseau..."
try {
    Copy-Item -LiteralPath $DownloadPath -Destination $DestPath -Force
    Write-OK "Nouveau fichier copie : $DestPath"
}
catch {
    Exit-WithError "Echec de la copie : $_"
}

# ========================
# NETTOYAGE : Supprimer le fichier dans Downloads
# ========================
Write-Step "Nettoyage du fichier temporaire dans Downloads..."
try {
    Remove-Item -LiteralPath $DownloadPath -Force -ErrorAction SilentlyContinue
    Write-OK "Fichier temporaire supprime."
}
catch {
    Write-Host "   (non critique) Impossible de supprimer le fichier temporaire." -ForegroundColor Yellow
}

# ========================
# ETAPE 6 : Executer le flux Tableau Prep via CLI
# ========================
$PrepCli  = "C:\Program Files\Tableau\Tableau Prep Builder 2025.1\scripts\tableau-prep-cli.bat"
$PrepFlow = Join-Path $env:USERPROFILE "Documents\Mon dossier Tableau Prep\Flux\Perimetre Migration.tfl"
$PrepLogDir = Join-Path $env:USERPROFILE "Documents\Mon dossier Tableau Prep\Journaux"
# Fichiers temporaires pour capturer la sortie du CLI
$PrepOutFile = Join-Path $PSScriptRoot "PrepBuilder_stdout.txt"
$PrepErrFile = Join-Path $PSScriptRoot "PrepBuilder_stderr.txt"

Write-Step "Execution du flux Tableau Prep : Perimetre Migration..."

# Nettoyage preventif : supprimer un eventuel _Updated.hyper residuel d'un run precedent
# (evite l'erreur "The database file is locked by another process")
$HyperUpdatedPreRun = Join-Path $DestDir "Perimetre_Migration_Updated.hyper"
if (Test-Path -LiteralPath $HyperUpdatedPreRun) {
    try {
        Remove-Item -LiteralPath $HyperUpdatedPreRun -Force -ErrorAction Stop
        Write-Host "   Nettoyage : ancien Perimetre_Migration_Updated.hyper supprime." -ForegroundColor Gray
    }
    catch {
        Write-Err "Impossible de supprimer $HyperUpdatedPreRun : $_"
        Write-Host "   Le fichier est peut-etre verrouille par un autre processus. Fermez Tableau Desktop/Prep et relancez." -ForegroundColor Yellow
    }
}

if (-not (Test-Path -LiteralPath $PrepCli)) {
    Write-Err "Tableau Prep CLI introuvable : $PrepCli"
    Write-Host "   Le transfert a bien fonctionne, mais le flux n'a pas pu etre execute." -ForegroundColor Yellow
}
elseif (-not (Test-Path -LiteralPath $PrepFlow)) {
    Write-Err "Flux introuvable : $PrepFlow"
    Write-Host "   Le transfert a bien fonctionne, mais le flux n'a pas pu etre execute." -ForegroundColor Yellow
}
else {
    try {
        $prepStartTime = Get-Date
        $maxAttempts = 3
        $attempt = 0
        $prepProcess = $null

        while ($attempt -lt $maxAttempts) {
            $attempt++
            if ($attempt -eq 1) {
                Write-Host "   Demarrage a $(Get-Date -Format 'HH:mm:ss') - veuillez patienter..." -ForegroundColor Gray
            } else {
                Write-Host "   Tentative $attempt/$maxAttempts a $(Get-Date -Format 'HH:mm:ss')..." -ForegroundColor Yellow
                # Nettoyage entre tentatives (l'ancien _Updated.hyper peut traîner apres un echec)
                if (Test-Path -LiteralPath $HyperUpdatedPreRun) {
                    Start-Sleep -Seconds 5  # laisser le temps aux handles SMB de se liberer
                    try {
                        Remove-Item -LiteralPath $HyperUpdatedPreRun -Force -ErrorAction Stop
                        Write-Host "   Orphelin nettoye entre tentatives." -ForegroundColor Gray
                    } catch {
                        Write-Host "   Impossible de nettoyer l'orphelin : $_" -ForegroundColor Yellow
                    }
                }
            }

            # Lancer le CLI Tableau Prep et attendre la fin
            $prepProcess = Start-Process -FilePath "cmd.exe" `
                -ArgumentList "/c `"`"$PrepCli`" -t `"$PrepFlow`"`"" `
                -Wait -NoNewWindow -PassThru `
                -RedirectStandardOutput $PrepOutFile `
                -RedirectStandardError $PrepErrFile

            if ($prepProcess.ExitCode -eq 0) { break }

            # Verifier si c'est bien une erreur de verrouillage SMB (auquel cas on retente)
            $prepStdout = if (Test-Path $PrepOutFile) { Get-Content $PrepOutFile -Raw -Encoding UTF8 } else { "" }
            $isLockError = $prepStdout -match "locked by another process"

            if ($isLockError -and $attempt -lt $maxAttempts) {
                Write-Host "   Erreur de verrou SMB detectee, nouvelle tentative apres pause..." -ForegroundColor Yellow
                Start-Sleep -Seconds 15
                continue
            }
            break  # echec non lie au verrou ou max tentatives atteint
        }

        $prepDuration = (Get-Date) - $prepStartTime
        $prepMinutes  = [math]::Floor($prepDuration.TotalMinutes)
        $prepSeconds  = $prepDuration.Seconds

        # Afficher le resultat
        if ($prepProcess.ExitCode -eq 0) {
            Write-OK "Flux execute avec succes en ${prepMinutes}m ${prepSeconds}s"

            # ========================
            # SWAP HYPER : Updated -> principal
            # Le flux ecrit dans Perimetre_Migration_Updated.hyper (input != output)
            # On remplace le fichier principal pour la prochaine execution + dashboard
            # ========================
            $HyperMain    = Join-Path $DestDir "Perimetre_Migration.hyper"
            $HyperUpdated = Join-Path $DestDir "Perimetre_Migration_Updated.hyper"
            $HyperBackup  = Join-Path $DestDir "Perimetre_Migration_PREVIOUS.hyper"

            if (Test-Path -LiteralPath $HyperUpdated) {
                Write-Step "Swap du fichier Hyper (Updated -> principal)..."
                try {
                    # Backup de l'ancien (si existe) -> _PREVIOUS pour rollback
                    if (Test-Path -LiteralPath $HyperMain) {
                        if (Test-Path -LiteralPath $HyperBackup) {
                            Remove-Item -LiteralPath $HyperBackup -Force
                        }
                        Move-Item -LiteralPath $HyperMain -Destination $HyperBackup -Force
                        Write-OK "Ancien Hyper sauvegarde : Perimetre_Migration_PREVIOUS.hyper"
                    }
                    # Promouvoir le nouveau
                    Move-Item -LiteralPath $HyperUpdated -Destination $HyperMain -Force
                    Write-OK "Nouveau Hyper en place : Perimetre_Migration.hyper"
                }
                catch {
                    Write-Err "Echec du swap Hyper : $_"
                    Write-Host "   Tentative de rollback..." -ForegroundColor Yellow
                    if ((Test-Path -LiteralPath $HyperBackup) -and (-not (Test-Path -LiteralPath $HyperMain))) {
                        Move-Item -LiteralPath $HyperBackup -Destination $HyperMain -Force
                        Write-Host "   Rollback effectue." -ForegroundColor Yellow
                    }
                }
            }
            else {
                Write-Err "Fichier $HyperUpdated introuvable apres execution du flux !"
            }

            # ================================================
            # EXECUTION DU FLUX JIRA (Traitement Jira.tfl)
            # Lit Jira.csv du partage, transforme (Domaine + Charge_Jours),
            # ecrit Jira_Projet.hyper
            # ================================================
            $JiraFlow = Join-Path $env:USERPROFILE "Documents\Mon dossier Tableau Prep\Flux\Traitement Jira.tfl"
            $JiraOutFile = Join-Path $PSScriptRoot "PrepJira_stdout.txt"
            $JiraErrFile = Join-Path $PSScriptRoot "PrepJira_stderr.txt"

            if (Test-Path -LiteralPath $JiraFlow) {
                Write-Step "Execution du flux Tableau Prep : Traitement Jira..."
                try {
                    $jiraStartTime = Get-Date
                    Write-Host "   Demarrage a $(Get-Date -Format 'HH:mm:ss')..." -ForegroundColor Gray

                    $jiraProcess = Start-Process -FilePath "cmd.exe" `
                        -ArgumentList "/c `"`"$PrepCli`" -t `"$JiraFlow`"`"" `
                        -Wait -NoNewWindow -PassThru `
                        -RedirectStandardOutput $JiraOutFile `
                        -RedirectStandardError $JiraErrFile

                    $jiraDuration = (Get-Date) - $jiraStartTime
                    $jiraSecs = [math]::Round($jiraDuration.TotalSeconds, 1)

                    if ($jiraProcess.ExitCode -eq 0) {
                        Write-OK "Flux Jira execute avec succes en ${jiraSecs}s"
                    } else {
                        Write-Err "Flux Jira termine avec code : $($jiraProcess.ExitCode)"
                        if (Test-Path $JiraOutFile) {
                            Get-Content $JiraOutFile -Encoding UTF8 -Tail 10 -ErrorAction SilentlyContinue | ForEach-Object {
                                Write-Host "   $_" -ForegroundColor Yellow
                            }
                        }
                    }
                    Remove-Item $JiraOutFile -Force -ErrorAction SilentlyContinue
                    Remove-Item $JiraErrFile -Force -ErrorAction SilentlyContinue
                }
                catch {
                    Write-Err "Echec de l'execution du flux Jira : $_"
                }
            }
            else {
                Write-Host "   (flux Jira introuvable a $JiraFlow, etape ignoree)" -ForegroundColor Gray
            }

            # ================================================
            # PUBLICATION TABLEAU SERVER (via REST API + PAT)
            # Publie Perimetre_Migration.hyper comme datasource
            # "Perimetre_Migration_Hyper" dans le projet "Published"
            # (avec overwrite) en utilisant le PAT de credentials.json
            # ================================================
            $CredFile = Join-Path $PSScriptRoot "credentials.json"
            $HyperToPublish = Join-Path $DestDir "Perimetre_Migration.hyper"

            if (-not (Test-Path -LiteralPath $CredFile)) {
                Write-Host "`n   (publication serveur ignoree : credentials.json introuvable)" -ForegroundColor Yellow
            }
            elseif (-not (Test-Path -LiteralPath $HyperToPublish)) {
                Write-Err "Hyper a publier introuvable : $HyperToPublish"
            }
            else {
                Write-Step "Publication de Perimetre_Migration_Hyper sur Tableau Server..."

                # Configuration
                $ApiVersion        = "3.22"
                $ProjectLuid       = "028b1ddb-7103-42ee-b91c-115c55df29c0"   # Project "Published" (sous-projet ISCS-BI > 02-Released > 00-DataSources > Published)
                $DatasourceName    = "Perimetre_Migration_Hyper"

                try {
                    # 1. Lire les credentials PAT
                    $cred = Get-Content -LiteralPath $CredFile -Raw -Encoding UTF8 | ConvertFrom-Json
                    $ServerUrl  = $cred.serverUrl
                    $ContentUrl = if ($cred.contentUrl) { $cred.contentUrl } else { "" }
                    $PatName    = $cred.personalAccessTokenName
                    $PatSecret  = $cred.personalAccessTokenSecret

                    if ([string]::IsNullOrWhiteSpace($PatName) -or [string]::IsNullOrWhiteSpace($PatSecret) -or $PatSecret -like "REMPLACE*") {
                        throw "PAT introuvable ou non rempli dans credentials.json"
                    }

                    Write-Host "   Server : $ServerUrl (PAT : $PatName)" -ForegroundColor Gray

                    # 2. Sign in via REST API
                    $signinUrl  = "$ServerUrl/api/$ApiVersion/auth/signin"
                    $signinXml  = "<tsRequest><credentials personalAccessTokenName=`"$PatName`" personalAccessTokenSecret=`"$PatSecret`"><site contentUrl=`"$ContentUrl`" /></credentials></tsRequest>"
                    $signin = Invoke-RestMethod -Uri $signinUrl -Method Post -Body $signinXml -ContentType "application/xml" -ErrorAction Stop
                    $AuthToken = $signin.tsResponse.credentials.token
                    $SiteId    = $signin.tsResponse.credentials.site.id
                    Write-OK "Authentification OK (site: $SiteId)"

                    # 3. Publish datasource (multipart POST) avec overwrite=true
                    # File upload simple (fonctionne bien pour < 64 MB, notre Hyper fait ~300 KB)
                    $publishUrl = "$ServerUrl/api/$ApiVersion/sites/$SiteId/datasources?datasourceType=hyper&overwrite=true"

                    $boundary = [System.Guid]::NewGuid().ToString()
                    $LF = "`r`n"
                    $requestPayloadXml = "<tsRequest><datasource name=`"$DatasourceName`"><project id=`"$ProjectLuid`" /></datasource></tsRequest>"

                    # Construire le body multipart manuellement (PowerShell 5.1 ne supporte pas -Form)
                    $fileBytes = [System.IO.File]::ReadAllBytes($HyperToPublish)
                    $fileName  = Split-Path $HyperToPublish -Leaf

                    $headerText = "--$boundary$LF" `
                        + "Content-Disposition: name=`"request_payload`"$LF" `
                        + "Content-Type: text/xml$LF$LF" `
                        + "$requestPayloadXml$LF" `
                        + "--$boundary$LF" `
                        + "Content-Disposition: name=`"tableau_datasource`"; filename=`"$fileName`"$LF" `
                        + "Content-Type: application/octet-stream$LF$LF"

                    $footerText = "$LF--$boundary--$LF"

                    $headerBytes = [System.Text.Encoding]::UTF8.GetBytes($headerText)
                    $footerBytes = [System.Text.Encoding]::UTF8.GetBytes($footerText)

                    $body = New-Object byte[] ($headerBytes.Length + $fileBytes.Length + $footerBytes.Length)
                    [Array]::Copy($headerBytes, 0, $body, 0, $headerBytes.Length)
                    [Array]::Copy($fileBytes, 0, $body, $headerBytes.Length, $fileBytes.Length)
                    [Array]::Copy($footerBytes, 0, $body, $headerBytes.Length + $fileBytes.Length, $footerBytes.Length)

                    $headers = @{ "X-Tableau-Auth" = $AuthToken }
                    $contentType = "multipart/mixed; boundary=$boundary"

                    Write-Host "   Upload du Hyper ($([math]::Round($fileBytes.Length / 1KB, 1)) KB)..." -ForegroundColor Gray
                    $publishStart = Get-Date
                    $publishResp = Invoke-RestMethod -Uri $publishUrl -Method Post -Headers $headers -Body $body -ContentType $contentType -ErrorAction Stop
                    $publishDuration = ((Get-Date) - $publishStart).TotalSeconds
                    $dsId = $publishResp.tsResponse.datasource.id
                    Write-OK ("Datasource publiee en {0:N1}s (id: {1})" -f $publishDuration, $dsId)

                    # 3bis. Publier aussi Jira_Projet.hyper si present (meme session auth)
                    $JiraHyper = Join-Path $DestDir "Jira_Projet.hyper"
                    if (Test-Path -LiteralPath $JiraHyper) {
                        Write-Step "Publication de Jira_Projet sur Tableau Server..."
                        try {
                            $jiraPublishUrl = "$ServerUrl/api/$ApiVersion/sites/$SiteId/datasources?datasourceType=hyper&overwrite=true"
                            $jiraBoundary   = [System.Guid]::NewGuid().ToString()
                            $jiraPayloadXml = "<tsRequest><datasource name=`"Jira_Projet`"><project id=`"$ProjectLuid`" /></datasource></tsRequest>"

                            $jiraFileBytes = [System.IO.File]::ReadAllBytes($JiraHyper)
                            $jiraFileName  = Split-Path $JiraHyper -Leaf

                            $jiraHeaderText = "--$jiraBoundary$LF" `
                                + "Content-Disposition: name=`"request_payload`"$LF" `
                                + "Content-Type: text/xml$LF$LF" `
                                + "$jiraPayloadXml$LF" `
                                + "--$jiraBoundary$LF" `
                                + "Content-Disposition: name=`"tableau_datasource`"; filename=`"$jiraFileName`"$LF" `
                                + "Content-Type: application/octet-stream$LF$LF"
                            $jiraFooterText = "$LF--$jiraBoundary--$LF"
                            $jiraHeaderBytes = [System.Text.Encoding]::UTF8.GetBytes($jiraHeaderText)
                            $jiraFooterBytes = [System.Text.Encoding]::UTF8.GetBytes($jiraFooterText)
                            $jiraBody = New-Object byte[] ($jiraHeaderBytes.Length + $jiraFileBytes.Length + $jiraFooterBytes.Length)
                            [Array]::Copy($jiraHeaderBytes, 0, $jiraBody, 0, $jiraHeaderBytes.Length)
                            [Array]::Copy($jiraFileBytes, 0, $jiraBody, $jiraHeaderBytes.Length, $jiraFileBytes.Length)
                            [Array]::Copy($jiraFooterBytes, 0, $jiraBody, $jiraHeaderBytes.Length + $jiraFileBytes.Length, $jiraFooterBytes.Length)

                            $jiraContentType = "multipart/mixed; boundary=$jiraBoundary"
                            Write-Host "   Upload du Jira_Projet.hyper ($([math]::Round($jiraFileBytes.Length / 1KB, 1)) KB)..." -ForegroundColor Gray
                            $jiraPublishStart = Get-Date
                            $jiraPublishResp = Invoke-RestMethod -Uri $jiraPublishUrl -Method Post -Headers $headers -Body $jiraBody -ContentType $jiraContentType -ErrorAction Stop
                            $jiraPublishDuration = ((Get-Date) - $jiraPublishStart).TotalSeconds
                            $jiraDsId = $jiraPublishResp.tsResponse.datasource.id
                            Write-OK ("Jira_Projet publiee en {0:N1}s (id: {1})" -f $jiraPublishDuration, $jiraDsId)
                        }
                        catch {
                            Write-Err "Echec de la publication Jira_Projet : $_"
                        }
                    }
                    else {
                        Write-Host "   (Jira_Projet.hyper introuvable, publication Jira ignoree)" -ForegroundColor Gray
                    }

                    # 4. Sign out
                    $signoutUrl = "$ServerUrl/api/$ApiVersion/auth/signout"
                    Invoke-RestMethod -Uri $signoutUrl -Method Post -Headers $headers -ErrorAction SilentlyContinue | Out-Null
                }
                catch {
                    Write-Err "Echec de la publication Tableau Server : $_"
                    if ($_.Exception.Response) {
                        try {
                            $errStream = $_.Exception.Response.GetResponseStream()
                            $reader = New-Object System.IO.StreamReader($errStream)
                            $errBody = $reader.ReadToEnd()
                            Write-Host "   Details : $errBody" -ForegroundColor Yellow
                        } catch { }
                    }
                    Write-Host "   Le .hyper reste dispo localement ; republiez manuellement si besoin." -ForegroundColor Yellow
                }
            }
        }
        else {
            Write-Err "Le flux s'est termine avec le code de sortie : $($prepProcess.ExitCode)"
        }

        # Afficher la sortie standard du CLI
        Write-Host "`n   --- Sortie Tableau Prep CLI ---" -ForegroundColor Cyan
        if (Test-Path $PrepOutFile) {
            $prepOutput = Get-Content $PrepOutFile -Encoding UTF8 -ErrorAction SilentlyContinue
            if ($prepOutput) {
                $prepOutput | ForEach-Object { Write-Host "   $_" -ForegroundColor White }
            }
            else {
                Write-Host "   (aucune sortie standard)" -ForegroundColor Gray
            }
        }

        # Afficher les erreurs s'il y en a
        if (Test-Path $PrepErrFile) {
            $prepErrors = Get-Content $PrepErrFile -Encoding UTF8 -ErrorAction SilentlyContinue
            if ($prepErrors) {
                Write-Host "`n   --- Erreurs Tableau Prep CLI ---" -ForegroundColor Yellow
                $prepErrors | ForEach-Object { Write-Host "   $_" -ForegroundColor Yellow }
            }
        }
        Write-Host "   --- Fin sortie Tableau Prep ---" -ForegroundColor Cyan

        # Nettoyage des fichiers temporaires de sortie
        Remove-Item $PrepOutFile -Force -ErrorAction SilentlyContinue
        Remove-Item $PrepErrFile -Force -ErrorAction SilentlyContinue
    }
    catch {
        Write-Err "Echec de l'execution du flux : $_"
        Write-Host "   Le transfert a bien fonctionne, mais le flux n'a pas pu etre execute." -ForegroundColor Yellow
    }
}

# ========================
# RESUME
# ========================
Write-Host "`n=========================================" -ForegroundColor Green
Write-Host "   SCRIPT TERMINE !" -ForegroundColor Green
Write-Host "=========================================" -ForegroundColor Green
Write-Host ""
Write-Host "   Source      : SharePoint EPFL" -ForegroundColor White
Write-Host "   Destination : $DestPath" -ForegroundColor White
Write-Host "   Archive     : $OldDir" -ForegroundColor White
Write-Host "   Flux Prep   : Perimetre Migration.tfl" -ForegroundColor White
Write-Host ""
Write-Host "   Log script  : $LogFile" -ForegroundColor Gray
Write-Host "   Logs Prep   : $PrepLogDir" -ForegroundColor Gray

Stop-Transcript -ErrorAction SilentlyContinue | Out-Null
Read-Host "`nAppuyez sur Entree pour fermer"
