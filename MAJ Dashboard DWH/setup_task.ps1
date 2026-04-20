$taskName = "MAJ Dashboard DWH - Transfert Inventaire"
$batPath  = Join-Path $PSScriptRoot "TransfertInventaire.bat"
$workDir  = $PSScriptRoot

$action   = New-ScheduledTaskAction -Execute $batPath -WorkingDirectory $workDir
$trigger  = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday -At "08:30"
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Description "Transfert automatique Inventaire de migration depuis SharePoint + execution flux Tableau Prep (lundi-vendredi 8h30)" -Force

Write-Host ""
Write-Host "Tache planifiee mise a jour avec succes !" -ForegroundColor Green
Write-Host "  Nom     : $taskName" -ForegroundColor White
Write-Host "  Quand   : Lundi au vendredi a 08h30" -ForegroundColor White
Write-Host "  Action  : $batPath" -ForegroundColor White
Write-Host ""
Write-Host "Pour verifier : Ouvrir Planificateur de taches > Bibliotheque > '$taskName'" -ForegroundColor Gray
Read-Host "Appuyez sur Entree pour fermer"
