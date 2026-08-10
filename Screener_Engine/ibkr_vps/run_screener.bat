@echo off
REM run_screener.bat — screener growth pre-cassure (Option C : Yahoo sur le VPS).
REM A planifier via le Planificateur de taches, chaque jour ouvre (~06:00).
REM Prerequis : venv cree (python -m venv .venv && .venv\Scripts\pip install -r requirements.txt).

cd /d "%~dp0"

REM --- Firebase (destination du classement, lu par le dashboard) ---
set "FIREBASE_DB_URL=https://portfolio-dashboard-f0c69-default-rtdb.firebaseio.com"
REM set "FIREBASE_DB_SECRET=colle_ton_secret_ici"   REM ou GOOGLE_APPLICATION_CREDENTIALS

REM --- Reglages du screener (tous optionnels, valeurs par defaut entre parentheses) ---
set "SCREEN_MIN_REVGROWTH=0.25"     REM croissance CA mini (0.25)
set "SCREEN_MAX_REVGROWTH=3.0"      REM borne haute anti-distorsion (3.0 = 300%)
set "SCREEN_MIN_MCAP=300000000"     REM cap mini (baisse pour plus de small caps)
set "UNIVERSE_LIMIT=250"            REM nb de titres enrichis
set "MAX_TOTAL=500"
set "TOP_N=50"

REM --- IBKR (optionnel : momentum precis + positions live) ---
set "ENABLE_IBKR=false"            REM true pour activer (IB Gateway doit tourner)
set "IBKR_PORT=4001"
set "IBKR_CLIENT_ID=17"
set "BLEND_IBKR=0.15"

if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" run.py %*
) else (
  python run.py %*
)
