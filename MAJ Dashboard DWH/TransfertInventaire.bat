@echo off
title Transfert Inventaire de migration
echo =========================================
echo   Transfert Inventaire de migration
echo =========================================
echo.
powershell -ExecutionPolicy Bypass -NoProfile -File "%~dp0TransfertInventaire.ps1"

echo.
echo --- Si une erreur s'est produite, consultez le fichier ---
echo --- TransfertInventaire_LOG.txt dans ce repertoire     ---
echo.
pause
