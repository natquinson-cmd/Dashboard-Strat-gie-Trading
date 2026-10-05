@echo off
REM live_prices.bat - cours "temps reel" des positions du dashboard.
REM Planifie via le Planificateur de taches TOUTES LES 5 MIN (tache DivKing_LivePrices, /RI 5).
REM Changer la cadence : schtasks /Change /TN "DivKing_LivePrices" /RI 5   (CMD administrateur)
REM Prerequis : meme venv que le screener (requirements.txt deja installe).

cd /d "%~dp0"

set "FIREBASE_DB_URL=https://portfolio-dashboard-f0c69-default-rtdb.firebaseio.com"
REM Cle secrete Firebase : JAMAIS dans ce fichier (depot public). Les scripts lisent la variable systeme
REM FIREBASE_DB_SECRET, posee une fois par setx /M (voir Securite_Firebase\LISEZMOI.md, test : verifier_cle.bat).

if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" live_prices.py
) else (
  python live_prices.py
)
