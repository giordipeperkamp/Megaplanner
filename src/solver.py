from __future__ import annotations

from typing import Dict, List, Tuple, Set, DefaultDict
from datetime import datetime

from ortools.sat.python import cp_model

from .models import Doctor, Location, Session, DoctorById, LocationById, SessionById, PreferenceScore, DoctorWeekRule, WorkdaysByDoctor


def _time_overlap(start_a, end_a, start_b, end_b) -> bool:
    # Overlap als intervallen elkaar snijden: a_start < b_end en b_start < a_end
    return (start_a < end_b) and (start_b < end_a)


def _build_overlap_pairs(sessions: List[Session]) -> Dict[str, List[str]]:
    # Per datum: markeer overlappende sessiepaaren
    by_date: Dict[str, List[Session]] = {}
    for s in sessions:
        key = s.date.isoformat()
        by_date.setdefault(key, []).append(s)
    overlaps: Dict[str, List[str]] = {}
    for day, sess_list in by_date.items():
        n = len(sess_list)
        for i in range(n):
            for j in range(i + 1, n):
                a = sess_list[i]
                b = sess_list[j]
                if _time_overlap(a.start_time, a.end_time, b.start_time, b.end_time):
                    overlaps.setdefault(a.session_id, []).append(b.session_id)
                    overlaps.setdefault(b.session_id, []).append(a.session_id)
    return overlaps


def solve_schedule(
    doctors: DoctorById,
    locations: LocationById,
    sessions: SessionById,
    preferences: PreferenceScore,
    travel_minutes: Dict[tuple, int] | None = None,
    workdays_by_doctor: WorkdaysByDoctor | None = None,
    week_rules: List[DoctorWeekRule] | None = None,
) -> Tuple[Dict[str, str], int]:
    """
    Retourneert:
      - assignments: dict session_id -> doctor_id
      - objective_value: totale voorkeursscore
    """
    doctor_list = list(doctors.values())
    session_list = list(sessions.values())

    doctor_index = {d.doctor_id: idx for idx, d in enumerate(doctor_list)}
    session_index = {s.session_id: idx for idx, s in enumerate(session_list)}

    model = cp_model.CpModel()

    # Helpers voor ritme
    def weekday1_7(dt) -> int:
        # Python: Monday=0..Sunday=6 -> 1..7
        return int(dt.weekday()) + 1

    def week_of_month1_5(dt) -> int:
        # Simpel: dagen 1-7 => 1, 8-14 => 2, 15-21 => 3, 22-28 => 4, 29-31 => 5
        return (int(dt.day) - 1) // 7 + 1

    if workdays_by_doctor is None:
        workdays_by_doctor = {}
    if week_rules is None:
        week_rules = []

    # Indexeer weekregels per (doctor_id, wom, weekday)
    rules_index: Dict[Tuple[str, int, int], Set[str]] = {}
    for r in week_rules:
        key = (r.doctor_id, int(r.week_of_month), int(r.weekday))
        rules_index.setdefault(key, set()).add(r.location_id)

    # Variabelen x[i,s] alleen voor toegestane combinaties (schaalt beter)
    x_vars: Dict[Tuple[int, int], cp_model.IntVar] = {}
    allowed_pairs: Dict[int, List[int]] = {}
    for i, d in enumerate(doctor_list):
        for s_idx, s in enumerate(session_list):
            # Beschikbaarheid op datum (onbeschikbaar wint altijd)
            if s.date in d.unavailable_dates:
                continue
            # Skill
            if s.required_skill and (s.required_skill not in d.skills):
                continue
            # Ritme: vaste werkdagen (optioneel) — uitzonderingen via available_dates
            wd = weekday1_7(s.date)
            wd_set = workdays_by_doctor.get(d.doctor_id)
            if wd_set is not None and len(wd_set) > 0 and wd not in wd_set:
                # alleen toestaan als expliciet als beschikbaar gezet
                avail_override = getattr(d, "available_dates", set())
                if s.date not in avail_override:
                    continue
            # Weekregel: als er regels zijn voor (week_of_month, weekday), dan alleen die locaties toestaan
            wom = week_of_month1_5(s.date)
            allowed_locs = rules_index.get((d.doctor_id, wom, wd))
            if allowed_locs is not None and len(allowed_locs) > 0 and s.location_id not in allowed_locs:
                continue
            var = model.NewBoolVar(f"x_{d.doctor_id}_{s.session_id}")
            x_vars[(i, s_idx)] = var
            allowed_pairs.setdefault(s_idx, []).append(i)

    # Elke sessie exact 1 arts
    for s_idx, s in enumerate(session_list):
        vars_for_session = [x_vars[(i, s_idx)] for i in allowed_pairs.get(s_idx, [])]
        if not vars_for_session:
            # Geen enkele arts kan deze sessie invullen -> infeasible
            # We kunnen ook optioneel soft maken, maar MVP: hard constraint
            model.AddBoolOr([])  # onoplosbare clause om infeasible te forceren
        else:
            model.Add(sum(vars_for_session) == 1)

    # Capaciteit per arts
    for i, d in enumerate(doctor_list):
        vars_for_doctor = [x_vars[(i, s_idx)] for (i2, s_idx) in x_vars.keys() if i2 == i]
        if vars_for_doctor:
            model.Add(sum(vars_for_doctor) <= d.max_sessions)

    # Geen overlap per arts op dezelfde dag
    overlaps_by_session = _build_overlap_pairs(session_list)
    for i, d in enumerate(doctor_list):
        for s_id, overlap_ids in overlaps_by_session.items():
            s_idx = session_index[s_id]
            if (i, s_idx) not in x_vars:
                continue
            for t_id in overlap_ids:
                t_idx = session_index[t_id]
                if (i, t_idx) not in x_vars:
                    continue
                # x[i,s] + x[i,t] <= 1
                model.Add(x_vars[(i, s_idx)] + x_vars[(i, t_idx)] <= 1)

    # Reistijd constraint: als tijd tussen sessies < travel_minutes(from,to), dan niet dezelfde arts
    if travel_minutes is None:
        travel_minutes = {}

    def get_travel(a_loc: str, b_loc: str) -> int:
        if a_loc == b_loc:
            return 0
        if (a_loc, b_loc) in travel_minutes:
            return int(travel_minutes[(a_loc, b_loc)])
        if (b_loc, a_loc) in travel_minutes:
            return int(travel_minutes[(b_loc, a_loc)])
        # Als onbekend: conservatief hoog (onhaalbaar na elkaar)
        return 10**6

    # Alleen paren op dezelfde dag (volgorde-respecterend)
    by_date: Dict[str, List[Session]] = {}
    for s in session_list:
        by_date.setdefault(s.date.isoformat(), []).append(s)
    for day, sess_list in by_date.items():
        # Sorteer op starttijd voor efficiënte checks
        sess_list_sorted = sorted(sess_list, key=lambda s: s.start_time)
        for idx_a, a in enumerate(sess_list_sorted):
            for idx_b in range(idx_a + 1, len(sess_list_sorted)):
                b = sess_list_sorted[idx_b]
                # a -> b volgorde
                required_gap = get_travel(a.location_id, b.location_id)
                # Beschikbare gap in minuten
                gap_minutes = (datetime.combine(a.date, b.start_time) - datetime.combine(a.date, a.end_time)).total_seconds() / 60.0
                if gap_minutes < required_gap:
                    a_idx = session_index[a.session_id]
                    b_idx = session_index[b.session_id]
                    for i, _d in enumerate(doctor_list):
                        if (i, a_idx) in x_vars and (i, b_idx) in x_vars:
                            model.Add(x_vars[(i, a_idx)] + x_vars[(i, b_idx)] <= 1)

    # Doelfunctie: max sum voorkeursscore(i, locatie(s)) * x[i,s]
    terms = []
    for (i, s_idx), var in x_vars.items():
        s = session_list[s_idx]
        d = doctor_list[i]
        score = int(preferences.get((d.doctor_id, s.location_id), 0))
        if score != 0:
            terms.append(score * var)
    if terms:
        model.Maximize(sum(terms))
    else:
        # Geen voorkeuren: arbitraire oplossing, minimaliseer som indices (stabieler)
        model.Maximize(0)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 20.0  # redelijke timeout voor MVP
    solver.parameters.num_search_workers = 8

    status = solver.Solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise ValueError("Geen oplossing gevonden (infeasible). Controleer capaciteit, skills en beschikbaarheid.")

    assignments: Dict[str, str] = {}
    for (i, s_idx), var in x_vars.items():
        if solver.BooleanValue(var):
            s = session_list[s_idx]
            d = doctor_list[i]
            assignments[s.session_id] = d.doctor_id

    objective = int(solver.ObjectiveValue())
    return assignments, objective


