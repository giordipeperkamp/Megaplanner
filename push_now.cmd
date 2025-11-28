@echo off
setlocal
cd /d "%~dp0"

echo [Megaplanner] Publiceren naar GitHub: giordipeperkamp/Megaplanner
echo.

REM Zorg dat git user identity bestaat (anders faalt commit)
git config --global user.name  >nul 2>&1
if errorlevel 1 (
  git config --global user.name "giordipeperkamp"
)
git config --global user.email >nul 2>&1
if errorlevel 1 (
  git config --global user.email "giordipeperkamp@users.noreply.github.com"
)

REM Probeert PowerShell publisher te draaien (met gh als beschikbaar).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0publish.ps1" -RepoOwner "giordipeperkamp" -RepoName "Megaplanner"

if %ERRORLEVEL% NEQ 0 (
  echo.
  echo [Publish] Er is iets misgegaan. Controleer of git/gh geinstalleerd zijn en of je bent aangemeld.
  echo Snel oplossen:
  echo   winget install --id Git.Git -e
  echo   winget install --id GitHub.cli -e
  echo   gh auth login
  echo en voer dit bestand opnieuw uit.
  pause
)

endlocal

