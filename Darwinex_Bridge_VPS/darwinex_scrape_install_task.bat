@echo off
REM ============================================================================
REM Enregistre la tâche planifiée Windows : collecte Darwinex chaque jour à 23h30.
REM À lancer UNE fois (clic droit > Exécuter en tant qu'administrateur si besoin),
REM APRÈS avoir fait "py darwinex_scrape_daily.py --login" et un "--once" de test.
REM ============================================================================
schtasks /Create /SC DAILY /ST 23:30 /TN "DarwinexScraperDaily" /TR "\"%~dp0darwinex_scrape_run.bat\"" /RL LIMITED /F

echo.
echo Tache creee : DarwinexScraperDaily (tous les jours a 23h30).
echo   Verifier : schtasks /Query /TN DarwinexScraperDaily
echo   Tester   : schtasks /Run   /TN DarwinexScraperDaily
echo   Supprimer: schtasks /Delete /TN DarwinexScraperDaily /F
echo.
pause
