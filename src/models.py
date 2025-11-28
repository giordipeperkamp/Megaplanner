from __future__ import annotations

from dataclasses import dataclass
from datetime import date, time
from typing import Dict, List, Optional, Set


@dataclass(frozen=True)
class Doctor:
    doctor_id: str
    name: str
    max_sessions: int
    unavailable_dates: Set[date]
    available_dates: Set[date]
    home_dates: Set[date]
    skills: Set[str]


@dataclass(frozen=True)
class Location:
    location_id: str
    name: str


@dataclass(frozen=True)
class Session:
    session_id: str
    date: date
    location_id: str
    start_time: time
    end_time: time
    required_skill: Optional[str] = None
    room: str = ""


@dataclass(frozen=True)
class Preference:
    doctor_id: str
    location_id: str
    score: int


DoctorById = Dict[str, Doctor]
LocationById = Dict[str, Location]
SessionById = Dict[str, Session]
PreferenceScore = Dict[tuple, int]  # (doctor_id, location_id) -> score


# Ritme/Regels
Weekday = int  # 1=ma, 7=zo


@dataclass(frozen=True)
class DoctorWeekRule:
    doctor_id: str
    week_of_month: int  # 1..5
    weekday: Weekday    # 1..7
    location_id: str


WorkdaysByDoctor = Dict[str, Set[Weekday]]
WeekRules = List[DoctorWeekRule]

