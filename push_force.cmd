@echo off
setlocal
cd /d "%~dp0"

set REPO_OWNER=giordipeperkamp
set REPO_NAME=Megaplanner2
set REPO_URL=https://github.com/%REPO_OWNER%/%REPO_NAME%.git

echo [Megaplanner] Force publish naar %REPO_OWNER%/%REPO_NAME%  (overschrijft remote geschiedenis indien nodig)
echo.

REM 1) Zorg dat git identity bestaat
git config --global user.name  >nul 2>&1
if errorlevel 1 git config --global user.name "%REPO_OWNER%"
git config --global user.email >nul 2>&1
if errorlevel 1 git config --global user.email "%REPO_OWNER%@users.noreply.github.com"

REM 2) Repo aanmaken als nodig (via gh)
where gh >nul 2>&1
if %ERRORLEVEL%==0 (
  gh repo view %REPO_OWNER%/%REPO_NAME% >nul 2>&1
  if errorlevel 1 (
    echo [GH] Maak nieuwe repo: %REPO_OWNER%/%REPO_NAME%
    gh repo create %REPO_OWNER%/%REPO_NAME% --public --source . --remote origin --push
    goto :EOF
  )
)

REM 3) Force push lokale inhoud
git init >nul 2>&1
git add -A
git commit -m "publish: force update" --allow-empty >nul 2>&1
git branch -M main >nul 2>&1
git remote remove origin >nul 2>&1
git remote add origin %REPO_URL% >nul 2>&1

echo.
echo [Git] push --force-with-lease naar %REPO_URL%
git push -u origin main --force-with-lease

echo.
echo Done. Repo: https://github.com/%REPO_OWNER%/%REPO_NAME%
echo Klaar. Volgende keer kun je opnieuw push_force.cmd draaien.

endlocal

