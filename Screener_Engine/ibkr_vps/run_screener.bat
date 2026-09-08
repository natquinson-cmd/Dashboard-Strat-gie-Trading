@echo off
REM run_screener.bat — screener du dashboard (Option C : Yahoo sur le VPS).
REM A planifier via le Planificateur de taches, chaque jour ouvre (~06:00).
REM Prerequis : venv cree (python -m venv .venv && .venv\Scripts\pip install -r requirements.txt).
REM
REM MODES (passes tels quels a run.py) :
REM   run_screener.bat --mode=quality   -> SEUL le classement qualite (grandes caps), celui que lit
REM                                        le dashboard : noeud stocks/screener/quality. RECOMMANDE.
REM   run_screener.bat --mode=smallcap  -> seulement le small/mid cap (abandonne).
REM   run_screener.bat                  -> les DEUX.
REM
REM Le script ecrit un JOURNAL dans .\logs\screener_AAAA-MM-JJ.log et renvoie le code de retour
REM de Python. Sans ca, un echec de la tache planifiee est totalement silencieux : le fichier de
REM ce script s'est retrouve VIDE sur le VPS et la tache a "reussi" a ne rien faire pendant 11 jours.

cd /d "%~dp0"

REM --- Firebase (destination du classement, lu par le dashboard) ---
set "FIREBASE_DB_URL=https://portfolio-dashboard-f0c69-default-rtdb.firebaseio.com"
REM set "FIREBASE_DB_SECRET=colle_ton_secret_ici"   REM ou GOOGLE_APPLICATION_CREDENTIALS

REM --- Reglages du screener SMALL/MID CAP uniquement (sans effet en --mode=quality) ---
set "SCREEN_MIN_REVGROWTH=0.30"      REM croissance CA mini (0.30)
set "SCREEN_MAX_REVGROWTH=3.0"       REM borne haute anti-distorsion (3.0 = 300%)
set "SCREEN_MIN_MCAP=500000000"      REM cap mini (500M)
set "SCREEN_MAX_MCAP=10000000000"    REM cap MAXI = exclut les mega caps
set "UNIVERSE_LIMIT=300"             REM nb de titres enrichis (les plus PETITS d'abord)
set "MAX_TOTAL=1000"
set "TOP_N=50"

REM --- IBKR (optionnel : momentum precis + positions live) ---
set "ENABLE_IBKR=false"            REM true pour activer (IB Gateway doit tourner)
set "IBKR_PORT=4001"
set "IBKR_CLIENT_ID=17"
set "BLEND_IBKR=0.15"

REM --- Journal date (PowerShell pour la date : %DATE% depend de la locale Windows) ---
set "LOGDIR=%~dp0logs"
if not exist "%LOGDIR%" mkdir "%LOGDIR%"
set "TODAY="
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd"') do set "TODAY=%%i"
if not defined TODAY set "TODAY=inconnu"
set "LOG=%LOGDIR%\screener_%TODAY%.log"

echo.>> "%LOG%"
echo ===== DEMARRAGE %DATE% %TIME%  args=[%*] =====>> "%LOG%"

if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" run.py %* 1>> "%LOG%" 2>&1
) else (
  python run.py %* 1>> "%LOG%" 2>&1
)
set "RC=%ERRORLEVEL%"

echo ===== FIN, code de retour %RC% =====>> "%LOG%"

REM Un lancement MANUEL n'affichait plus rien du tout, toute la sortie partant dans le journal.
REM On rend donc la fin du journal a l'ecran. (PowerShell sert seulement a LIRE le fichier : on ne
REM fait surtout pas passer la sortie de Python par un pipe PowerShell, qui en 5.1 transforme
REM chaque ligne de stderr en erreur et fait passer un run reussi pour un echec.)
echo.
echo --- dernieres lignes du journal ---
powershell -NoProfile -Command "Get-Content -LiteralPath '%LOG%' -Tail 25"
echo -----------------------------------
echo Journal complet : %LOG%
echo Pour suivre un run EN DIRECT depuis une autre fenetre :
echo   powershell -NoProfile -Command "Get-Content -LiteralPath '%LOG%' -Wait -Tail 30"
if not "%RC%"=="0" echo ECHEC du screener, code de retour %RC%.
exit /b %RC%
