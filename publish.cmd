@echo off
setlocal
cd /d "%~dp0"

REM Run PowerShell publisher (installs nothing; uses gh if available)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0publish.ps1" -RepoOwner "giordipeperkamp" -RepoName "Megaplanner"

if %ERRORLEVEL% NEQ 0 (
  echo.
  echo [Publish] Er is iets misgegaan. Controleer of git is geinstalleerd en of je toegang hebt tot GitHub.
  pause
)

endlocal

