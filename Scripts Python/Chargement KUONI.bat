@echo off
chcp 65001 >nul
title Chargement KUONI - EPFL CO2 Report Travel

echo ============================================================
echo   Chargement KUONI - EPFL CO2 Report Travel
echo   %date% %time%
echo ============================================================
echo.

cd /d "%~dp0"

"C:\Users\quinson\AppData\Local\Python\bin\python.exe" "Chargement KUONI.py"

echo.
if %ERRORLEVEL% EQU 0 (
    echo [OK] Traitement termine avec succes.
) else (
    echo [ERREUR] Le traitement a echoue. Voir les messages ci-dessus.
)

echo.
echo Appuyez sur une touche pour fermer...
pause >nul
