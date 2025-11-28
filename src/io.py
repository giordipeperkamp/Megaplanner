from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple
from datetime import date, time, datetime

import pandas as pd
from dateutil import parser as dtparser

from .models import Doctor, Location, Session, Preference, DoctorById, LocationById, SessionById, PreferenceScore, DoctorWeekRule, WorkdaysByDoctor, Weekday


def _split_tokens(value: str) -> List[str]:
    if value is None:
        return []
    s = str(value).strip()
    if not s:
        return []
    # Lists are semicolon-separated by conventie
    return [t.strip() for t in s.split(";") if t.strip()]


def _parse_date(value: str) -> date:
    return dtparser.parse(str(value)).date()


def _parse_time(value: str) -> time:
    # Verwacht HH:MM, maar parser is tolerant
    parsed = dtparser.parse(str(value))
    return time(hour=parsed.hour, minute=parsed.minute, second=parsed.second)


def read_doctors(path: str | Path) -> DoctorById:
    df = pd.read_csv(path, dtype=str).fillna("")
    required_cols = {"doctor_id", "name", "max_sessions", "unavailable_dates", "available_dates", "home_dates", "skills"}
    missing = required_cols.difference(set(df.columns))
    if missing:
        raise ValueError(f"Ontbrekende kolommen in doctors: {missing}")

    doctors: Dict[str, Doctor] = {}
    for _, row in df.iterrows():
        doctor_id = row["doctor_id"].strip()
        if not doctor_id:
            continue
        name = row["name"].strip() or doctor_id
        try:
            max_sessions = int(str(row["max_sessions"]).strip() or "0")
        except ValueError:
            raise ValueError(f"max_sessions moet geheel getal zijn voor arts {doctor_id}")

        unavailable_dates_raw = _split_tokens(row["unavailable_dates"])
        unavailable_dates: Set[date] = set(_parse_date(d) for d in unavailable_dates_raw)
        available_dates_raw = _split_tokens(row.get("available_dates", ""))
        available_dates: Set[date] = set(_parse_date(d) for d in available_dates_raw)
        home_dates_raw = _split_tokens(row.get("home_dates", ""))
        home_dates: Set[date] = set(_parse_date(d) for d in home_dates_raw)
        skills = set(t.lower() for t in _split_tokens(row["skills"]))

        doctors[doctor_id] = Doctor(
            doctor_id=doctor_id,
            name=name,
            max_sessions=max_sessions,
            unavailable_dates=unavailable_dates,
            available_dates=available_dates,
            home_dates=home_dates,
            skills=skills,
        )
    return doctors


def read_locations(path: str | Path) -> LocationById:
    df = pd.read_csv(path, dtype=str).fillna("")
    required_cols = {"location_id", "name"}
    missing = required_cols.difference(set(df.columns))
    if missing:
        raise ValueError(f"Ontbrekende kolommen in locations: {missing}")

    locations: Dict[str, Location] = {}
    for _, row in df.iterrows():
        location_id = row["location_id"].strip()
        if not location_id:
            continue
        name = row["name"].strip() or location_id
        locations[location_id] = Location(location_id=location_id, name=name)
    return locations


def read_sessions(path: str | Path) -> SessionById:
    df = pd.read_csv(path, dtype=str).fillna("")
    required_cols = {"session_id", "date", "location_id", "start_time", "end_time", "required_skill"}
    missing = required_cols.difference(set(df.columns))
    if missing:
        raise ValueError(f"Ontbrekende kolommen in sessions: {missing}")

    sessions: Dict[str, Session] = {}
    for _, row in df.iterrows():
        session_id = row["session_id"].strip()
        if not session_id:
            continue
        session_date = _parse_date(row["date"])
        location_id = row["location_id"].strip()
        start_time = _parse_time(row["start_time"])
        end_time = _parse_time(row["end_time"])
        required_skill_raw = str(row["required_skill"]).strip()
        required_skill = required_skill_raw.lower() if required_skill_raw else None
        # Optionele kolom: room
        room = ""
        if "room" in df.columns:
            room = str(row["room"]).strip()
        sessions[session_id] = Session(
            session_id=session_id,
            date=session_date,
            location_id=location_id,
            start_time=start_time,
            end_time=end_time,
            required_skill=required_skill,
            room=room,
        )
    return sessions


def read_travel_times(path: Optional[str | Path]) -> Dict[tuple, int]:
    """
    Leest reistijden tussen locaties (in minuten).
    Verwacht kolommen: from_location_id,to_location_id,minutes
    """
    if path is None:
        return {}
    df = pd.read_csv(path, dtype=str).fillna("")
    required_cols = {"from_location_id", "to_location_id", "minutes"}
    missing = required_cols.difference(set(df.columns))
    if missing:
        raise ValueError(f"Ontbrekende kolommen in travel_times: {missing}")
    tt: Dict[tuple, int] = {}
    for _, row in df.iterrows():
        a = row["from_location_id"].strip()
        b = row["to_location_id"].strip()
        try:
            m = int(str(row["minutes"]).strip())
        except ValueError:
            raise ValueError(f"minutes moet geheel getal zijn voor {a}->{b}")
        if a and b:
            tt[(a, b)] = m
    return tt


def read_preferences(path: Optional[str | Path]) -> PreferenceScore:
    if path is None:
        return {}
    df = pd.read_csv(path, dtype=str).fillna("")
    required_cols = {"doctor_id", "location_id", "score"}
    missing = required_cols.difference(set(df.columns))
    if missing:
        raise ValueError(f"Ontbrekende kolommen in preferences: {missing}")

    prefs: PreferenceScore = {}
    for _, row in df.iterrows():
        doctor_id = row["doctor_id"].strip()
        location_id = row["location_id"].strip()
        if not (doctor_id and location_id):
            continue
        try:
            score = int(str(row["score"]).strip())
        except ValueError:
            raise ValueError(f"score moet geheel getal zijn voor preference {doctor_id}-{location_id}")
        prefs[(doctor_id, location_id)] = score
    return prefs


def ensure_parent_dir(path: str | Path) -> None:
    p = Path(path)
    if p.parent and not p.parent.exists():
        p.parent.mkdir(parents=True, exist_ok=True)


def write_schedule_csv(
    path: str | Path,
    assignments: Dict[str, str],
    doctors: DoctorById,
    locations: LocationById,
    sessions: SessionById,
) -> None:
    ensure_parent_dir(path)
    rows = []
    for session_id, doctor_id in assignments.items():
        s = sessions[session_id]
        d = doctors[doctor_id]
        loc = locations.get(s.location_id)
        rows.append({
            "session_id": s.session_id,
            "date": s.date.isoformat(),
            "location_id": s.location_id,
            "location_name": (loc.name if loc else s.location_id),
            "doctor_id": d.doctor_id,
            "doctor_name": d.name,
            "start_time": s.start_time.strftime("%H:%M"),
            "end_time": s.end_time.strftime("%H:%M"),
            "required_skill": s.required_skill or "",
            "room": getattr(s, "room", "") or "",
        })
    pd.DataFrame(rows).sort_values(["date", "location_id", "start_time"]).to_csv(path, index=False)


_WEEKDAY_MAP = {
    "1": 1, "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7,
    "ma": 1, "maandag": 1, "mon": 1, "monday": 1,
    "di": 2, "dinsdag": 2, "tue": 2, "tuesday": 2,
    "wo": 3, "woensdag": 3, "wed": 3, "wednesday": 3,
    "do": 4, "donderdag": 4, "thu": 4, "thursday": 4,
    "vr": 5, "vrijdag": 5, "fri": 5, "friday": 5,
    "za": 6, "zaterdag": 6, "sat": 6, "saturday": 6,
    "zo": 7, "zondag": 7, "sun": 7, "sunday": 7,
}


def _parse_weekday(value: str) -> Weekday:
    key = str(value).strip().lower()
    if key in _WEEKDAY_MAP:
        return _WEEKDAY_MAP[key]
    try:
        v = int(key)
        if 1 <= v <= 7:
            return v
    except ValueError:
        pass
    raise ValueError(f"Onbekende weekday: {value}")


def read_doctor_workdays(path: Optional[str | Path]) -> WorkdaysByDoctor:
    """
    CSV: doctor_id,weekday
    1=ma, ..., 7=zo. Ook 'ma', 'di', etc. toegestaan.
    """
    if path is None:
        return {}
    df = pd.read_csv(path, dtype=str).fillna("")
    required_cols = {"doctor_id", "weekday"}
    missing = required_cols.difference(set(df.columns))
    if missing:
        raise ValueError(f"Ontbrekende kolommen in doctor_workdays: {missing}")
    workdays: WorkdaysByDoctor = {}
    for _, row in df.iterrows():
        doctor_id = row["doctor_id"].strip()
        if not doctor_id:
            continue
        wd = _parse_weekday(row["weekday"])
        workdays.setdefault(doctor_id, set()).add(wd)
    return workdays


def read_doctor_week_rules(path: Optional[str | Path]) -> List[DoctorWeekRule]:
    """
    CSV: doctor_id,week_of_month,weekday,location_id
    - week_of_month: 1..5 (1=1e t/m 7e dag, 2=8e t/m 14e, ...)
    - weekday: 1..7 of namen ('ma', ...)
    """
    if path is None:
        return []
    df = pd.read_csv(path, dtype=str).fillna("")
    required_cols = {"doctor_id", "week_of_month", "weekday", "location_id"}
    missing = required_cols.difference(set(df.columns))
    if missing:
        raise ValueError(f"Ontbrekende kolommen in doctor_week_rules: {missing}")
    rules: List[DoctorWeekRule] = []
    for _, row in df.iterrows():
        doctor_id = row["doctor_id"].strip()
        if not doctor_id:
            continue
        try:
            wom = int(str(row["week_of_month"]).strip())
        except ValueError:
            raise ValueError(f"week_of_month moet 1..5 zijn voor arts {doctor_id}")
        if wom < 1 or wom > 5:
            raise ValueError(f"week_of_month buiten bereik (1..5) voor arts {doctor_id}")
        wd = _parse_weekday(row["weekday"])
        loc = row["location_id"].strip()
        if not loc:
            continue
        rules.append(DoctorWeekRule(doctor_id=doctor_id, week_of_month=wom, weekday=wd, location_id=loc))
    return rules

