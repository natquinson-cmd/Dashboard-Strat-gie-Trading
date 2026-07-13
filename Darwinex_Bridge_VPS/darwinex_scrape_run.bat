@echo off
REM Lance la collecte quotidienne Darwinex (appelé par la tâche planifiée 23h30).
cd /d "%~dp0"
py darwinex_scrape_daily.py --once >> darwinex_scrape.log 2>&1
