@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [Setup] Virtuele omgeving aanmaken...
    python -m venv .venv
)
call .venv\Scripts\activate.bat

echo [Setup] Dependencies installeren/controle...
pip install -r requirements.txt

set ADDRESS=127.0.0.1
set PORT=8502
echo [Start] GUI openen op http://%ADDRESS%:%PORT% ...
start "" http://%ADDRESS%:%PORT%
streamlit run src/app.py --server.address %ADDRESS% --server.port %PORT%

echo.
echo Klaar. Dit venster sluiten om te stoppen.
pause

image.png