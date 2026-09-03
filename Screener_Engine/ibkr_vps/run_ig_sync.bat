@echo off
REM run_ig_sync.bat - synchronisation IG -> Firebase, sans navigateur.
REM A planifier via le Planificateur de taches, TOUS LES JOURS A 23:00.
REM Prerequis : venv cree, et ig_config.json rempli avec tes identifiants IG.

cd /d "%~dp0"

set "FIREBASE_DB_URL=https://portfolio-dashboard-f0c69-default-rtdb.firebaseio.com"

if not exist "ig_config.json" (
  echo ERREUR : ig_config.json manquant. Copie ig_config.example.json en ig_config.json et remplis tes identifiants IG.
  exit /b 1
)

echo ==== Synchro IG %DATE% %TIME% ====
".venv\Scripts\python.exe" ig_sync.py %*
echo ==== Fin (code %ERRORLEVEL%) ====
