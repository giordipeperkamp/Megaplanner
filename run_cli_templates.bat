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

echo [Run] Planner draaien met voorbeelddata...
python -m src.cli ^
  --doctors "data\templates\doctors.csv" ^
  --locations "data\templates\locations.csv" ^
  --sessions "data\templates\sessions.csv" ^
  --preferences "data\templates\preferences.csv" ^
  --travel_times "data\templates\travel_times.csv" ^
  --doctor_workdays "data\templates\doctor_workdays.csv" ^
  --doctor_week_rules "data\templates\doctor_week_rules.csv" ^
  --output "output\schedule.csv"

echo.
echo Gereed. Open: output\schedule.csv
pause

