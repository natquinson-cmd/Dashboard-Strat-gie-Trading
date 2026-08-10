@echo off
REM run_screener.bat — screener growth pre-cassure (Option C : Yahoo sur le VPS).
REM A planifier via le Planificateur de taches, chaque jour ouvre (~06:00).
REM Prerequis : venv cree (python -m venv .venv && .venv\Scripts\pip install -r requirements.txt).

cd /d "%~dp0"

REM --- Firebase (destination du classement, lu par le dashboard) ---
set "FIREBASE_DB_URL=https://portfolio-dashboard-f0c69-default-rtdb.firebaseio.com"
REM set "FIREBASE_DB_SECRET=colle_ton_secret_ici"   REM ou GOOGLE_APPLICATION_CREDENTIALS

REM --- Reglages du screener (tous optionnels, valeurs par defaut entre parentheses) ---
REM Cible SMALL/MID caps "pretes a exploser", mega caps EXCLUES.
set "SCREEN_MIN_REVGROWTH=0.30"      REM croissance CA mini (0.30)
set "SCREEN_MAX_REVGROWTH=3.0"       REM borne haute anti-distorsion (3.0 = 300%)
set "SCREEN_MIN_MCAP=500000000"      REM cap mini (500M)
set "SCREEN_MAX_MCAP=10000000000"    REM cap MAXI = exclut les mega caps. Baisse (ex 3000000000) pour cibler plus petit
set "UNIVERSE_LIMIT=300"             REM nb de titres enrichis (les plus PETITS d'abord)
set "MAX_TOTAL=1000"
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
