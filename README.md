## Automatische Planner voor Bedrijfsartsen (MVP)

Deze MVP maakt automatisch maandroosters op basis van CSV-bestanden met:
- artsen (capaciteit, beschikbaarheid, skills)
- locaties
- spreekuur-sessies (datum/tijd/locatie, optioneel vereiste skill)
- voorkeuren (score per arts-locatie)

De planner gebruikt OR-Tools (CP-SAT) om een optimaal rooster te vinden.

### Installatie (Windows/PowerShell)
1. Optioneel: maak en activeer een virtual environment
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```
2. Installeer dependencies
   ```powershell
   pip install -r requirements.txt
   ```

### Snel starten met voorbeelddata
Er zijn sjablonen én voorbeelddata aanwezig in `data\templates`.

```powershell
python -m src.cli `
  --doctors "data\templates\doctors.csv" `
  --locations "data\templates\locations.csv" `
  --sessions "data\templates\sessions.csv" `
  --preferences "data\templates\preferences.csv" `
  --travel_times "data\templates\travel_times.csv" `
  --doctor_workdays "data\templates\doctor_workdays.csv" `
  --doctor_week_rules "data\templates\doctor_week_rules.csv" `
  --output "output\schedule.csv"
```

Resultaat wordt weggeschreven naar `output\schedule.csv`.

### GUI gebruiken (Streamlit)
Start de eenvoudige GUI (browser):
```powershell
streamlit run src/app.py
```
In de GUI kun je:
- Overzicht (simpel): locaties en kamers bekijken en snel toevoegen
- Tabellen bewerken (artsen, locaties, rooms, sessies, voorkeuren, reistijden, ritme)
- Optioneel Excel uploaden met tabbladen (Doctors, Locations, Sessions, Preferences, TravelTimes, DoctorWorkdays, DoctorWeekRules)
- Sessies genereren op basis van weekregels voor een datumbereik (bijv. rest van het jaar)
- Met één klik plannen en als CSV/Excel downloaden

Opslaan/Exporteren in de GUI:
- “Opslaan naar CSV’s” → `data/custom/*.csv` (inclusief `rooms.csv`)
- “Opslaan als Excel” → `data/custom/megaplanner_data.xlsx` (inclusief tabblad “Rooms`”)

### “Play”-knop of dubbelklikken
- Cursor/VS Code: open het project, ga naar Run and Debug en kies “Run GUI (Streamlit)”, of druk op F5. (Wij leverden `.vscode/launch.json` mee.)
- Windows dubbelklikken:
  - `run_gui.bat`: start de GUI op `http://127.0.0.1:8502` (forceert adres/poort).
  - `run_cli_templates.bat`: snelle rooktest zonder GUI; schrijft `output\schedule.csv`.

Als `localhost` niet opent:
- Gebruik direct `http://127.0.0.1:8502`
- Controleer of geen andere app poort 8502 gebruikt (bestand `run_gui.bat` kun je aanpassen naar een andere poort)

### CSV-formaten
- `doctors.csv`
  - kolommen: `doctor_id,name,max_sessions,unavailable_dates,skills`
  - `unavailable_dates`: datums gescheiden door `;` (formaat YYYY-MM-DD), bv: `2025-12-05;2025-12-12`
  - `skills`: tokens gescheiden door `;` (bv: `algemeen;cardio`). Laat leeg als geen specifieke skills.

- `locations.csv`
  - kolommen: `location_id,name,default_start_time,default_end_time`

- `rooms.csv` (optioneel)
  - kolommen: `room_id,location_id,name`
  - Kamers vallen onder locaties; bij genereren wordt automatisch de enige kamer gekozen als er precies één is.

- `sessions.csv`
  - kolommen: `session_id,date,location_id,start_time,end_time,required_skill,room`
  - `date`: `YYYY-MM-DD`
  - `start_time`/`end_time`: `HH:MM` (24-uurs)
  - `required_skill`: laat leeg als elke arts kan
  - `room`: optioneel, bv. `Kamer 1.3`

- `preferences.csv` (optioneel)
  - kolommen: `doctor_id,location_id,score`
  - `score`: hoe hoger, hoe liever deze arts op die locatie (mag negatief zijn)

- `travel_times.csv` (optioneel)
  - kolommen: `from_location_id,to_location_id,minutes`
  - Reistijd per richting; laat weg of zet 0 voor gelijke locatie

- `doctor_workdays.csv` (optioneel, ritme)
  - kolommen: `doctor_id,weekday`
  - `weekday`: 1..7 of `ma,di,wo,do,vr,za,zo` (1=ma, 7=zo)
  - Beperkingen: arts is alleen inplanbaar op deze vaste weekdagen

- `doctor_week_rules.csv` (optioneel, ritme)
  - kolommen: `doctor_id,week_of_month,weekday,location_id`
  - `week_of_month`: 1..5 (1=1–7 van de maand, 2=8–14, ...)
  - Op die dag in die week mag de arts alleen op de gegeven `location_id` gepland worden

### Beperkingen (MVP)
- Elke sessie krijgt precies 1 arts
- Artscapaciteit per maand: `max_sessions`
- Arts is niet ingepland op eigen `unavailable_dates`
- Geen overlap per arts op dezelfde dag (tijdvakken mogen niet botsen)
- Skills: arts moet vereiste skill bezitten als de sessie die vereist
- Ritme: vaste werkdagen en weekregels worden als harde beperkingen toegepast
- Doel: maximale som van voorkeursscores

### Uitbreidingen (volgende stappen)
- Excel in- en uitvoer i.p.v. CSV (behoud van huidige werkwijze)
- Voorkeuren per sessie/dag (in plaats van per locatie)
- Min/max per dag per arts, reistijd tussen locaties, regio’s/klant-toewijzingen
- Fairness (gelijke verdeling), harde/soepele constraints met penalties
- Webinterface met upload/download en validatie

### Problemen oplossen
- Infeasible (geen oplossing): controleer capaciteit, skills en beschikbaarheden
- Controleer kolomnamen exact zoals hierboven


