from __future__ import annotations

import argparse
from pathlib import Path
import sys

from .io import read_doctors, read_locations, read_sessions, read_preferences, read_travel_times, write_schedule_csv, read_doctor_workdays, read_doctor_week_rules
from .solver import solve_schedule


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Automatische planner voor bedrijfsartsen (MVP)")
    p.add_argument("--doctors", required=True, help="Pad naar doctors.csv")
    p.add_argument("--locations", required=True, help="Pad naar locations.csv")
    p.add_argument("--sessions", required=True, help="Pad naar sessions.csv")
    p.add_argument("--preferences", required=False, default=None, help="Pad naar preferences.csv (optioneel)")
    p.add_argument("--travel_times", required=False, default=None, help="Pad naar travel_times.csv (optioneel)")
    p.add_argument("--doctor_workdays", required=False, default=None, help="Pad naar doctor_workdays.csv (optioneel)")
    p.add_argument("--doctor_week_rules", required=False, default=None, help="Pad naar doctor_week_rules.csv (optioneel)")
    p.add_argument("--output", required=False, default="output/schedule.csv", help="Uitvoer CSV-bestand")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    doctors = read_doctors(args.doctors)
    locations = read_locations(args.locations)
    sessions = read_sessions(args.sessions)
    preferences = read_preferences(args.preferences)
    travel_times = read_travel_times(args.travel_times)
    workdays = read_doctor_workdays(args.doctor_workdays)
    week_rules = read_doctor_week_rules(args.doctor_week_rules)

    assignments, objective = solve_schedule(doctors, locations, sessions, preferences, travel_times, workdays, week_rules)
    write_schedule_csv(args.output, assignments, doctors, locations, sessions)
    print(f"Rooster geschreven naar: {args.output} (totale voorkeursscore = {objective})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


