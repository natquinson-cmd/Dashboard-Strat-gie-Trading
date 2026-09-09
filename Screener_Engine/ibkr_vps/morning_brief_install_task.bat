@echo off
chcp 65001 >nul
REM Installe la tache planifiee du brief matinal : chaque jour a 07h45, donc pret
REM avant 8h30. A lancer UNE FOIS, en administrateur.

schtasks /Create /SC DAILY /ST 07:45 /TN "MorningBrief" /TR "\"%~dp0morning_brief.bat\"" /RL LIMITED /F

echo.
echo Tache creee : MorningBrief (tous les jours a 07h45).
echo   Verifier : schtasks /Query /TN MorningBrief
echo   Tester   : schtasks /Run   /TN MorningBrief
echo   Supprimer: schtasks /Delete /TN MorningBrief /F
echo.
echo RAPPEL : pose ta cle Anthropic une seule fois, toi-meme :
echo     setx ANTHROPIC_API_KEY "ta-cle-ici"
echo   puis ferme et rouvre l'invite de commandes.
echo.
pause
