@echo off
REM verifier_cle.bat - verifie que la cle secrete Firebase (variable systeme FIREBASE_DB_SECRET) est posee et
REM valide sur ce VPS, sans l'afficher. A lancer APRES le setx /M, dans une nouvelle fenetre (ou par double-clic).

cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" verifier_cle.py
) else (
  python verifier_cle.py
)
pause
