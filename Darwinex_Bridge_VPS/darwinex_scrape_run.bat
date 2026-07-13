@echo off
REM Collecte quotidienne Darwinex (appelée par la tâche planifiée à 00h30).
REM --backfill : recalcule chaque jour à sa vraie date -> la veille (complète) reçoit
REM son P&L final, et c'est auto-correctif (comble tout trou). Idempotent.
cd /d "%~dp0"
py darwinex_scrape_daily.py --backfill >> darwinex_scrape.log 2>&1
