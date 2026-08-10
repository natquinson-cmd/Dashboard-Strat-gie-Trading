@echo off
REM run_screener.bat — lance l'enrichissement IBKR + push Firebase (VPS Windows).
REM A planifier via le Planificateur de taches, apres l'heure du cron du Worker FMP.
REM Prerequis : IB Gateway lance et logue (via IBC), venv cree, variables ci-dessous.

cd /d "%~dp0"

REM --- Configuration (a adapter) ---
set "WORKER_URL=https://stock-screener.TON-SOUS-DOMAINE.workers.dev"
set "FIREBASE_DB_URL=https://portfolio-dashboard-f0c69-default-rtdb.firebaseio.com"
REM set "FIREBASE_DB_SECRET=colle_ton_secret_ici"   REM ou GOOGLE_APPLICATION_CREDENTIALS
set "IBKR_HOST=127.0.0.1"
set "IBKR_PORT=4001"
set "IBKR_CLIENT_ID=17"
set "TOP_N=40"
set "BLEND_IBKR=0.15"

REM --- Venv (cree une fois : python -m venv .venv && .venv\Scripts\pip install -r requirements.txt) ---
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" run.py %*
) else (
  python run.py %*
)
