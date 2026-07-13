@echo off
REM Collecte quotidienne Darwinex (appelée par la tâche planifiée à 00h30).
REM S'assure d'abord que le Chrome débogué (port 9222) tourne, puis --backfill.
REM --backfill : recalcule chaque jour à sa vraie date -> la veille (complète) reçoit
REM son P&L final, et c'est auto-correctif (comble tout trou). Idempotent.
cd /d "%~dp0"

REM Le Chrome débogué tourne-t-il déjà ? sinon, le lancer et attendre.
powershell -NoProfile -Command "try{(Invoke-WebRequest -UseBasicParsing http://localhost:9222/json/version -TimeoutSec 3)|Out-Null;exit 0}catch{exit 1}" >nul 2>&1
if errorlevel 1 (
  call "%~dp0start_chrome_debug.bat"
  timeout /t 8 >nul
)

py darwinex_scrape_daily.py --backfill >> darwinex_scrape.log 2>&1
