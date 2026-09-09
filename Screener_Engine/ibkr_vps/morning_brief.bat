@echo off
chcp 65001 >nul
REM morning_brief.bat - brief matinal du dashboard (Fear & Greed + actus + synthese).
REM A planifier CHAQUE JOUR OUVRE vers 07h45, pour etre pret avant 8h30.
REM Installation de la tache : morning_brief_install_task.bat
REM
REM CLE ANTHROPIC : elle n'est PAS dans ce fichier et ne doit JAMAIS y etre (le
REM dossier est versionne). Tu la poses une seule fois, toi-meme, en variable
REM d'environnement utilisateur, dans une invite de commandes :
REM
REM     setx ANTHROPIC_API_KEY "ta-cle-ici"
REM
REM Puis FERME et rouvre l'invite (setx n'affecte que les nouveaux processus).
REM Sans cette cle le script tourne quand meme : il pousse le Fear & Greed et les
REM titres bruts, seule la synthese redigee manque.
REM
REM MODELE : Haiku 4.5 par defaut, suffisant pour resumer des titres. Pour en changer :
REM     setx ANTHROPIC_MODEL "claude-opus-5"
REM Le nombre de tokens est le meme quel que soit le modele, seul le prix du token change.

cd /d "%~dp0"

set "FIREBASE_DB_URL=https://portfolio-dashboard-f0c69-default-rtdb.firebaseio.com"

REM --- Journal date, meme principe que le screener : un echec ne doit pas etre muet ---
set "LOGDIR=%~dp0logs"
if not exist "%LOGDIR%" mkdir "%LOGDIR%"
set "TODAY="
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd"') do set "TODAY=%%i"
if not defined TODAY set "TODAY=inconnu"
set "LOG=%LOGDIR%\morning_brief_%TODAY%.log"

echo.>> "%LOG%"
echo ===== DEMARRAGE %DATE% %TIME% =====>> "%LOG%"
if not defined ANTHROPIC_API_KEY echo [!] ANTHROPIC_API_KEY absente : pas de synthese redigee.>> "%LOG%"

if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" morning_brief.py 1>> "%LOG%" 2>&1
) else (
  python morning_brief.py 1>> "%LOG%" 2>&1
)
set "RC=%ERRORLEVEL%"
echo ===== FIN, code de retour %RC% =====>> "%LOG%"

echo.
echo --- dernieres lignes du journal ---
powershell -NoProfile -Command "Get-Content -LiteralPath '%LOG%' -Tail 20"
echo -----------------------------------
echo Journal complet : %LOG%
if not "%RC%"=="0" echo ECHEC du brief matinal, code de retour %RC%.
exit /b %RC%
