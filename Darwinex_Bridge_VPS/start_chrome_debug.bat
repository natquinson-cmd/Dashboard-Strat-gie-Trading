@echo off
REM ============================================================================
REM Lance un VRAI Chrome en mode débogage (port 9222), profil dédié, sur ta page
REM portefeuille Darwinex. Connecte-toi dedans NORMALEMENT (le login marche, ce
REM n'est pas un navigateur piloté). Coche « Keep me logged in » et laisse ouvert.
REM Le scraper s'y branche ensuite pour lire les données.
REM Si Chrome est déjà lancé avec ce profil, ça ouvre juste un onglet (sans risque).
REM ============================================================================
set "PROFILE=%~dp0chrome_profile"
set "CHROME=%ProgramFiles%\Google\Chrome\Application\chrome.exe"
if not exist "%CHROME%" set "CHROME=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"
if not exist "%CHROME%" set "CHROME=%LocalAppData%\Google\Chrome\Application\chrome.exe"
if not exist "%CHROME%" (
  echo [ERREUR] chrome.exe introuvable. Installe Google Chrome puis relance.
  pause
  exit /b 1
)
start "" "%CHROME%" --remote-debugging-port=9222 --user-data-dir="%PROFILE%" "https://www.darwinex.com/fr/portfolio/chart"
