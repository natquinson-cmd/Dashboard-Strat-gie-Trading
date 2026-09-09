@echo off
chcp 65001 >nul
REM Sentinelle du bouton "Rafraichir" du brief matinal.
REM Toutes les MINUTES, elle regarde si le dashboard a demande un rafraichissement
REM (noeud dashboard/morningBriefRequest) et ne relance le brief que dans ce cas.
REM Sans demande, elle sort immediatement : deux petites lectures Firebase, rien de plus.
REM A lancer UNE FOIS, en administrateur.

schtasks /Create /SC MINUTE /MO 1 /TN "MorningBriefOnDemand" /TR "\"%~dp0morning_brief.bat\" --if-requested" /RL LIMITED /F

echo.
echo Tache creee : MorningBriefOnDemand (toutes les minutes, ne fait rien sans demande).
echo   Verifier : schtasks /Query /TN MorningBriefOnDemand
echo   Supprimer: schtasks /Delete /TN MorningBriefOnDemand /F
echo.
echo Elle est INDEPENDANTE de la tache MorningBrief de 07h45, qui reste en place.
echo.
pause
