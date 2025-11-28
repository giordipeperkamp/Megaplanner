from __future__ import annotations

import io
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import pandas as pd
import streamlit as st

# Compatibele imports: werk zowel als pakket (python -m) als los script (streamlit run src/app.py)
try:
    from .io import (  # type: ignore
        read_doctors,
        read_locations,
        read_sessions,
        read_preferences,
        read_travel_times,
        read_doctor_workdays,
        read_doctor_week_rules,
        write_schedule_csv,
    )
    from .models import Session  # type: ignore
    from .solver import solve_schedule  # type: ignore
except Exception:
    import sys as _sys
    _root = Path(__file__).resolve().parents[1]
    if str(_root) not in _sys.path:
        _sys.path.insert(0, str(_root))
    from src.io import (  # type: ignore
        read_doctors,
        read_locations,
        read_sessions,
        read_preferences,
        read_travel_times,
        read_doctor_workdays,
        read_doctor_week_rules,
        write_schedule_csv,
    )
    from src.models import Session  # type: ignore
    from src.solver import solve_schedule  # type: ignore


st.set_page_config(page_title="Megaplanner - Planner", layout="wide")
st.title("Megaplanner - Planner (MVP GUI)")

# Moduskeuze
mode = st.sidebar.radio("Modus", ["Overzicht (simpel)", "Beheer (tabel)", "Agenda (planning)"], index=0)


def load_csv_df(path: str, required_cols: List[str]) -> pd.DataFrame:
    p = Path(path)
    if p.exists():
        df = pd.read_csv(p, dtype=str).fillna("")
    else:
        df = pd.DataFrame(columns=required_cols)
    # force kolomvolgorde
    for c in required_cols:
        if c not in df.columns:
            df[c] = ""
    return df[required_cols]


def _csv_template(columns: List[str], example_rows: List[List[str]]) -> str:
    df = pd.DataFrame(example_rows, columns=columns)
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue()


def _excel_template_sheets(sheets: Dict[str, Dict[str, List]] ) -> bytes:
    """
    sheets: { sheet_name: { 'columns': [...], 'rows': [[...], ...] } }
    """
    bio = io.BytesIO()
    with pd.ExcelWriter(bio, engine="openpyxl") as writer:
        for sheet, spec in sheets.items():
            df = pd.DataFrame(spec.get("rows", []), columns=spec.get("columns", []))
            df.to_excel(writer, index=False, sheet_name=sheet)
    return bio.getvalue()


def _wd_to_int(value) -> Optional[int]:
    """Converteer weekday naar int 1..7; ondersteunt 'ma','di',... en cijfers."""
    mapping = {"ma": 1, "di": 2, "wo": 3, "do": 4, "vr": 5, "za": 6, "zo": 7}
    s = str(value).strip().lower()
    if s in mapping:
        return mapping[s]
    try:
        v = int(s)
        if 1 <= v <= 7:
            return v
    except Exception:
        return None
    return None


def _required_map() -> Dict[str, List[str]]:
    return {
        "doctors": ["doctor_id", "name", "max_sessions", "unavailable_dates", "available_dates", "home_dates", "skills"],
        "locations": ["location_id", "name", "default_start_time", "default_end_time"],
        "rooms": ["room_id", "location_id", "name"],
        "sessions": ["session_id", "date", "location_id", "start_time", "end_time", "required_skill", "room"],
        "preferences": ["doctor_id", "location_id", "score"],
        "travel_times": ["from_location_id", "to_location_id", "minutes"],
        "doctor_workdays": ["doctor_id", "weekday"],
        "doctor_week_rules": ["doctor_id", "week_of_month", "weekday", "location_id"],
    }


def _load_from_excel_if_exists(path: Path) -> Optional[Dict[str, pd.DataFrame]]:
    if not path.exists():
        return None
    try:
        xls = pd.ExcelFile(path)
        req = _required_map()
        dfs: Dict[str, pd.DataFrame] = {}
        sheet_names = {
            "Doctors": "doctors",
            "Locations": "locations",
            "Rooms": "rooms",
            "Sessions": "sessions",
            "Preferences": "preferences",
            "TravelTimes": "travel_times",
            "DoctorWorkdays": "doctor_workdays",
            "DoctorWeekRules": "doctor_week_rules",
        }
        for sheet, key in sheet_names.items():
            if sheet in xls.sheet_names:
                df = pd.read_excel(path, sheet_name=sheet, dtype=str).fillna("")
                cols = req[key]
                for c in cols:
                    if c not in df.columns:
                        df[c] = ""
                dfs[key] = df[cols]
            else:
                dfs[key] = pd.DataFrame(columns=req[key])
        return dfs
    except Exception:
        return None


def _load_from_custom_csvs(dir_path: Path) -> Optional[Dict[str, pd.DataFrame]]:
    if not dir_path.exists():
        return None
    req = _required_map()
    keys = list(req.keys())
    # Als geen enkel CSV-bestand bestaat, sla over
    if not any((dir_path / f"{k}.csv").exists() for k in keys):
        return None
    dfs: Dict[str, pd.DataFrame] = {}
    for k in keys:
        p = dir_path / f"{k}.csv"
        if p.exists():
            dfs[k] = load_csv_df(p, req[k])
        else:
            dfs[k] = pd.DataFrame(columns=req[k])
    return dfs


def _save_all_to_custom(dfs: Dict[str, pd.DataFrame]) -> None:
    out_dir = Path("data/custom")
    out_dir.mkdir(parents=True, exist_ok=True)
    for k, cols in _required_map().items():
        df = dfs.get(k, pd.DataFrame(columns=cols)).copy()
        # force kolomvolgorde
        for c in cols:
            if c not in df.columns:
                df[c] = ""
        df[cols].to_csv(out_dir / f"{k}.csv", index=False)


def load_initial_data() -> Dict[str, pd.DataFrame]:
    # 1) Probeer eerst custom CSV's (altijd meest actueel door autosave)
    dfs = _load_from_custom_csvs(Path("data/custom"))
    if dfs is not None:
        return dfs
    # 2) Zo niet, probeer custom Excel bundel
    dfs = _load_from_excel_if_exists(Path("data/custom/megaplanner_data.xlsx"))
    if dfs is not None:
        return dfs
    # 3) Fallback naar templates
    base = Path("data/templates")
    req = _required_map()
    return {k: load_csv_df(base / f"{k}.csv", cols) for k, cols in req.items()}


state = st.session_state
if "dfs" not in state:
    state.dfs = load_initial_data()

def _autosave():
    try:
        _save_all_to_custom(state.dfs)
    except Exception:
        pass

with st.expander("Optioneel: Excel-bestand uploaden (meerdere tabbladen)"):
    uploaded = st.file_uploader("Upload Excel (.xlsx) met tabbladen: Doctors, Locations, Sessions, Preferences, TravelTimes, DoctorWorkdays, DoctorWeekRules", type=["xlsx"])
    if uploaded is not None:
        xls = pd.ExcelFile(uploaded)
        sheet_map = {
            "Doctors": ("doctors", ["doctor_id", "name", "max_sessions", "unavailable_dates", "skills"]),
            "Locations": ("locations", ["location_id", "name", "default_start_time", "default_end_time"]),
            "Rooms": ("rooms", ["room_id", "location_id", "name"]),
            "Sessions": ("sessions", ["session_id", "date", "location_id", "start_time", "end_time", "required_skill", "room"]),
            "Preferences": ("preferences", ["doctor_id", "location_id", "score"]),
            "TravelTimes": ("travel_times", ["from_location_id", "to_location_id", "minutes"]),
            "DoctorWorkdays": ("doctor_workdays", ["doctor_id", "weekday"]),
            "DoctorWeekRules": ("doctor_week_rules", ["doctor_id", "week_of_month", "weekday", "location_id"]),
        }
        for sheet, (key, cols) in sheet_map.items():
            if sheet in xls.sheet_names:
                df = pd.read_excel(uploaded, sheet_name=sheet, dtype=str).fillna("")
                # align kolommen
                for c in cols:
                    if c not in df.columns:
                        df[c] = ""
                state.dfs[key] = df[cols]
        st.success("Excel geladen in werkgeheugen.")
        _autosave()

if mode == "Beheer (tabel)":
    st.subheader("Data bewerken")
    tabs = st.tabs(["Doctors", "Locations", "Rooms", "Sessions", "Preferences", "TravelTimes", "DoctorWorkdays", "DoctorWeekRules"])
    keys = ["doctors", "locations", "rooms", "sessions", "preferences", "travel_times", "doctor_workdays", "doctor_week_rules"]
    for t, key in zip(tabs, keys):
        with t:
            st.caption(f"Bewerk de tabel: {key}")
            original_df = state.dfs[key]
            edited = st.data_editor(original_df, num_rows="dynamic", use_container_width=True)
            edited = edited.fillna("")
            try:
                changed = not edited.equals(original_df)
            except Exception:
                changed = True
            if changed:
                state.dfs[key] = edited
                _autosave()
                st.caption("Automatisch opgeslagen naar data/custom.")
else:
    st.subheader("Overzicht")
    tab_locs, tab_docs_wd = st.tabs(["Locaties & Kamers", "Artsen & Werkdagen"])

    # TAB 1: Locaties & Kamers
    with tab_locs:
        left, right = st.columns([1, 2])
        with left:
            st.markdown("Snel toevoegen")
            # Bulk import locaties (CSV/Excel) met hulp-popover
            imp_c1, imp_c2 = st.columns([3, 1])
            with imp_c1:
                st.caption("Bulk import locaties (CSV of Excel)")
            with imp_c2:
                with st.popover("❓ Uitleg"):
                    st.markdown(
                        "- Kolommen verplicht: `location_id,name,default_start_time,default_end_time`\n"
                        "- Voorbeeld CSV:\n"
                        "  - L10,Locatie Noord,09:00,17:00\n"
                        "  - L11,Locatie Zuid,08:30,16:30\n"
                        "- Tijden: HH:MM (24-uurs)\n"
                        "- Import voegt toe; vink aan om bestaande te overschrijven op `location_id`."
                    )
            tmp1, tmp2, tmp3 = st.columns(3)
            with tmp1:
                st.download_button(
                    "Template CSV - locations",
                    data=_csv_template(
                        ["location_id","name","default_start_time","default_end_time"],
                        [["L10","Locatie Noord","09:00","17:00"]]
                    ),
                    file_name="locations_template.csv",
                    mime="text/csv"
                )
            with tmp2:
                st.download_button(
                    "Template CSV - rooms",
                    data=_csv_template(
                        ["room_id","location_id","name"],
                        [["R1","L10","Kamer 1.1"]]
                    ),
                    file_name="rooms_template.csv",
                    mime="text/csv"
                )
            with tmp3:
                excel_bytes = _excel_template_sheets({
                    "Locations": {"columns": ["location_id","name","default_start_time","default_end_time"], "rows":[["L10","Locatie Noord","09:00","17:00"]]},
                    "Rooms": {"columns": ["room_id","location_id","name"], "rows":[["R1","L10","Kamer 1.1"]]},
                })
                st.download_button("Template Excel (Locaties+Rooms)", data=excel_bytes, file_name="locations_rooms_template.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            uploaded_loc = st.file_uploader("Kies bestand (CSV/XLSX)", type=["csv", "xlsx"], key="bulk_locations_file")
            overwrite = st.checkbox("Bestaande overschrijven (op location_id)", value=False, key="bulk_locations_overwrite")
            if st.button("Importeer locaties", disabled=uploaded_loc is None):
                try:
                    if uploaded_loc.name.lower().endswith(".xlsx"):
                        df_new = pd.read_excel(uploaded_loc, dtype=str).fillna("")
                    else:
                        df_new = pd.read_csv(uploaded_loc, dtype=str).fillna("")
                    required = ["location_id", "name", "default_start_time", "default_end_time"]
                    missing = [c for c in required if c not in df_new.columns]
                    if missing:
                        raise ValueError(f"Ontbrekende kolommen: {missing}")
                    df_new = df_new[required]
                    loc_df = state.dfs["locations"].copy()
                    if overwrite:
                        merged = pd.concat([loc_df, df_new], ignore_index=True)
                        merged = merged.drop_duplicates(subset=["location_id"], keep="last")
                    else:
                        existing = set(loc_df["location_id"].astype(str).str.strip())
                        add = df_new[~df_new["location_id"].astype(str).str.strip().isin(existing)]
                        merged = pd.concat([loc_df, add], ignore_index=True)
                    state.dfs["locations"] = merged.fillna("")
                    st.success(f"Import gereed: {len(df_new)} rijen verwerkt.")
                    _autosave()
                except Exception as e:
                    st.error(f"Import mislukt: {e}")
            with st.form("add_location_form"):
                st.caption("Nieuwe locatie")
                new_loc_id = st.text_input("location_id", key="new_loc_id")
                new_loc_name = st.text_input("name", key="new_loc_name")
                new_loc_start = st.text_input("default_start_time", value="09:00", key="new_loc_start")
                new_loc_end = st.text_input("default_end_time", value="17:00", key="new_loc_end")
                submit_loc = st.form_submit_button("Locatie toevoegen")
                if submit_loc:
                    loc_df = state.dfs["locations"].copy()
                    if new_loc_id and new_loc_id not in set(loc_df["location_id"].astype(str)):
                        loc_df.loc[len(loc_df)] = [new_loc_id, new_loc_name, new_loc_start, new_loc_end]
                        state.dfs["locations"] = loc_df
                        st.success(f"Locatie toegevoegd: {new_loc_name or new_loc_id}")
                        _autosave()
                    else:
                        st.error("location_id ontbreekt of bestaat al.")
            with st.form("add_room_form"):
                st.caption("Nieuwe kamer")
                loc_df = state.dfs["locations"]
                loc_options = [(r["name"] or r["location_id"], r["location_id"]) for _, r in loc_df.iterrows()]
                selected_loc_label = st.selectbox("Locatie", [label for label, _ in loc_options], key="room_loc_label")
                selected_loc_id = dict(loc_options).get(selected_loc_label, None)
                new_room_id = st.text_input("room_id", key="new_room_id")
                new_room_name = st.text_input("room name", key="new_room_name")
                submit_room = st.form_submit_button("Kamer toevoegen")
                if submit_room:
                    if not selected_loc_id:
                        st.error("Kies een locatie.")
                    else:
                        rooms_df = state.dfs["rooms"].copy()
                        if new_room_id and new_room_id not in set(rooms_df["room_id"].astype(str)):
                            rooms_df.loc[len(rooms_df)] = [new_room_id, selected_loc_id, new_room_name]
                            state.dfs["rooms"] = rooms_df
                            st.success(f"Kamer toegevoegd aan {selected_loc_label}.")
                            _autosave()
                        else:
                            st.error("room_id ontbreekt of bestaat al.")
        with right:
            st.markdown("Locaties en kamers")
            loc_df = state.dfs["locations"].copy()
            rooms_df = state.dfs["rooms"].copy()
            for _, loc in loc_df.sort_values(["name", "location_id"]).iterrows():
                lid = str(loc["location_id"]).strip()
                lname = str(loc["name"]).strip() or lid
                with st.expander(f"{lname} ({lid})", expanded=False):
                    st.text(f"Standaardtijden: {str(loc.get('default_start_time',''))} - {str(loc.get('default_end_time',''))}")
                    # Bewerken van locatie
                    st.caption("Bewerk locatie")
                    with st.form(f"edit_location_{lid}"):
                        edit_name = st.text_input("name", value=str(loc.get("name", "")))
                        edit_start = st.text_input("default_start_time", value=str(loc.get("default_start_time", "")))
                        edit_end = st.text_input("default_end_time", value=str(loc.get("default_end_time", "")))
                        btn_save_edit = st.form_submit_button("Opslaan wijzigingen")
                        if btn_save_edit:
                            locs_df = state.dfs["locations"].copy()
                            idx_list = locs_df.index[locs_df["location_id"].astype(str).str.strip() == lid].tolist()
                            if idx_list:
                                i = idx_list[0]
                                locs_df.at[i, "name"] = edit_name
                                locs_df.at[i, "default_start_time"] = edit_start
                                locs_df.at[i, "default_end_time"] = edit_end
                                state.dfs["locations"] = locs_df
                                st.success("Locatie bijgewerkt.")
                                _autosave()
                    rms = rooms_df[rooms_df["location_id"].astype(str).str.strip() == lid]
                    if len(rms) == 0:
                        st.caption("Nog geen kamers")
                    else:
                        st.caption("Kamers")
                        st.table(rms[["room_id", "name"]].reset_index(drop=True))
                    st.caption("Bewerk kamers voor deze locatie")
                    with st.form(f"edit_rooms_{lid}"):
                        edit_rooms = st.data_editor(
                            rms[["room_id","name"]].reset_index(drop=True),
                            num_rows="dynamic",
                            use_container_width=True,
                            key=f"rooms_editor_{lid}"
                        )
                        if st.form_submit_button("Opslaan kamers"):
                            rooms2 = state.dfs["rooms"].copy()
                            # verwijder bestaande kamers voor deze locatie
                            rooms2 = rooms2[rooms2["location_id"].astype(str).str.strip() != lid]
                            # voeg bewerkte kamers toe
                            for _, r in edit_rooms.fillna("").iterrows():
                                rid = str(r["room_id"]).strip()
                                rname = str(r["name"]).strip()
                                if rid:
                                    rooms2.loc[len(rooms2)] = [rid, lid, rname]
                            state.dfs["rooms"] = rooms2
                            _autosave()
                            st.success("Kamers opgeslagen.")

    # TAB 2: Artsen (informatie en toevoegen)
    with tab_docs_wd:
        left, right = st.columns([1,2])
        with left:
            with st.form("add_doctor_form"):
                st.caption("Nieuwe arts")
                doc_id = st.text_input("doctor_id", key="new_doc_id")
                doc_name = st.text_input("name", key="new_doc_name")
                doc_max = st.text_input("max_sessions", value="10", key="new_doc_max")
                doc_unavail = st.text_input("unavailable_dates (YYYY-MM-DD;...)", value="", key="new_doc_unavail")
                doc_skills = st.text_input("skills (gescheiden door ;)", value="algemeen", key="new_doc_skills")
                submit_doc = st.form_submit_button("Arts toevoegen")
                if submit_doc:
                    try:
                        docs_df = state.dfs["doctors"].copy()
                        if doc_id and doc_id not in set(docs_df["doctor_id"].astype(str)):
                            try:
                                _ = int(str(doc_max).strip())
                            except Exception:
                                raise ValueError("max_sessions moet een geheel getal zijn.")
                            docs_df.loc[len(docs_df)] = [doc_id, doc_name, int(doc_max), doc_unavail, doc_skills]
                            state.dfs["doctors"] = docs_df
                            st.success(f"Arts opgeslagen: {doc_name or doc_id}")
                            _autosave()
                        else:
                            st.error("doctor_id ontbreekt of bestaat al.")
                    except Exception as e:
                        st.error(f"Opslaan mislukt: {e}")
            st.caption("Bulk import artsen (CSV/XLSX)")
            with st.popover("❓ Uitleg artsen"):
                st.markdown(
                    "- Kolommen: `doctor_id,name,max_sessions,unavailable_dates,available_dates,skills`\n"
                    "- Voorbeeld: D10,Dr. Janssen,12,2025-12-05;2025-12-12,algemeen;cardio"
                )
            dcol1, dcol2 = st.columns(2)
            with dcol1:
                st.download_button(
                    "Template CSV - doctors",
                    data=_csv_template(
                        ["doctor_id","name","max_sessions","unavailable_dates","skills"],
                        [["D10","Dr. Janssen","12","2025-12-05;2025-12-12","algemeen;cardio"]]
                    ),
                    file_name="doctors_template.csv",
                    mime="text/csv"
                )
            with dcol2:
                excel_bytes_docs = _excel_template_sheets({
                    "Doctors": {"columns": ["doctor_id","name","max_sessions","unavailable_dates","skills"], "rows":[["D10","Dr. Janssen","12","2025-12-05;2025-12-12","algemeen;cardio"]]}
                })
                st.download_button("Template Excel (Doctors)", data=excel_bytes_docs, file_name="doctors_template.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            up_docs = st.file_uploader("Bestand artsen", type=["csv","xlsx"], key="bulk_docs_file_v2")
            if st.button("Importeer artsen", disabled=up_docs is None, key="btn_import_docs_v2"):
                try:
                    if up_docs.name.lower().endswith(".xlsx"):
                        df_new = pd.read_excel(up_docs, dtype=str).fillna("")
                    else:
                        df_new = pd.read_csv(up_docs, dtype=str).fillna("")
                    req = ["doctor_id","name","max_sessions","unavailable_dates","skills"]
                    miss = [c for c in req if c not in df_new.columns]
                    if miss:
                        raise ValueError(f"Ontbrekende kolommen: {miss}")
                    df_new = df_new[req]
                    docs_df = state.dfs["doctors"].copy()
                    merged = pd.concat([docs_df, df_new], ignore_index=True)
                    merged = merged.drop_duplicates(subset=["doctor_id"], keep="last")
                    state.dfs["doctors"] = merged
                    st.success(f"Artsen geïmporteerd: {len(df_new)} rijen.")
                    _autosave()
                except Exception as e:
                    st.error(f"Import artsen mislukt: {e}")
        with right:
            st.markdown("Bewerk arts-informatie")
            docs_df = state.dfs["doctors"].copy()
            for _, drow in docs_df.sort_values(["name","doctor_id"]).iterrows():
                did = str(drow["doctor_id"]).strip()
                dname = str(drow["name"]).strip() or did
                with st.expander(f"{dname} ({did})", expanded=False):
                    with st.form(f"edit_doc_{did}"):
                        e_name = st.text_input("name", value=str(drow.get("name","")))
                        e_max = st.text_input("max_sessions", value=str(drow.get("max_sessions","")))
                        e_unavail = st.text_input("unavailable_dates", value=str(drow.get("unavailable_dates","")))
                        e_avail = st.text_input("available_dates", value=str(drow.get("available_dates","")))
                        e_skills = st.text_input("skills", value=str(drow.get("skills","")))
                        if st.form_submit_button("Opslaan"):
                            docs2 = state.dfs["doctors"].copy()
                            idxs = docs2.index[docs2["doctor_id"].astype(str).str.strip() == did].tolist()
                            if idxs:
                                i = idxs[0]
                                # validatie max_sessions
                                try:
                                    _ = int(str(e_max).strip()) if str(e_max).strip() != "" else 0
                                except Exception:
                                    st.error("max_sessions moet een geheel getal zijn.")
                                docs2.at[i,"name"] = e_name
                                docs2.at[i,"max_sessions"] = str(e_max).strip()
                                docs2.at[i,"unavailable_dates"] = e_unavail
                                docs2.at[i,"available_dates"] = e_avail
                                docs2.at[i,"skills"] = e_skills
                                state.dfs["doctors"] = docs2
                                _autosave()
                                st.success("Arts bijgewerkt.")

                    # Standaard werkdagen (ma–zo) per arts
                    st.caption("Standaard werkdagen (ma–zo)")
                    wd_tbl = state.dfs["doctor_workdays"]
                    wd_series = wd_tbl[wd_tbl["doctor_id"].astype(str).str.strip() == did]["weekday"]
                    current_wd = set([v for v in ( _wd_to_int(x) for x in wd_series.tolist() ) if v is not None])
                    day_labels = ["ma","di","wo","do","vr","za","zo"]
                    day_vals = [1,2,3,4,5,6,7]
                    cols_days = st.columns(7)
                    chosen = {}
                    for idx, (lbl, val) in enumerate(zip(day_labels, day_vals)):
                        chosen[val] = cols_days[idx].checkbox(lbl.upper(), value=(val in current_wd), key=f"wd_{did}_{val}")
                    col_actions = st.columns(3)
                    with col_actions[0]:
                        if st.button("Ma–vr", key=f"wd_btn_wd_{did}"):
                            new_set = {1,2,3,4,5}
                            df2 = state.dfs["doctor_workdays"].copy()
                            df2 = df2[df2["doctor_id"].astype(str).str.strip() != did]
                            for v in new_set:
                                df2.loc[len(df2)] = [did, v]
                            state.dfs["doctor_workdays"] = df2
                            _autosave()
                            st.success("Vaste werkdagen ingesteld: ma–vr.")
                    with col_actions[1]:
                        if st.button("Alle dagen", key=f"wd_btn_all_{did}"):
                            new_set = {1,2,3,4,5,6,7}
                            df2 = state.dfs["doctor_workdays"].copy()
                            df2 = df2[df2["doctor_id"].astype(str).str.strip() != did]
                            for v in new_set:
                                df2.loc[len(df2)] = [did, v]
                            state.dfs["doctor_workdays"] = df2
                            _autosave()
                            st.success("Vaste werkdagen ingesteld: alle dagen.")
                    with col_actions[2]:
                        if st.button("Geen", key=f"wd_btn_none_{did}"):
                            df2 = state.dfs["doctor_workdays"].copy()
                            df2 = df2[df2["doctor_id"].astype(str).str.strip() != did]
                            state.dfs["doctor_workdays"] = df2
                            _autosave()
                            st.success("Vaste werkdagen gewist.")
                    if st.button("Opslaan werkdagen", key=f"wd_save_{did}"):
                        new_set = {val for val, flag in chosen.items() if flag}
                        df2 = state.dfs["doctor_workdays"].copy()
                        df2 = df2[df2["doctor_id"].astype(str).str.strip() != did]
                        for v in sorted(new_set):
                            df2.loc[len(df2)] = [did, v]
                        state.dfs["doctor_workdays"] = df2
                        _autosave()
                        st.success("Vaste werkdagen opgeslagen.")

                    # Mini-kalender voor onbeschikbare dagen
                    st.caption("Onbeschikbare dagen (mini-kalender)")

                    def _parse_date_list(value: str) -> set[date]:
                        vals = set()
                        for part in str(value or "").split(";"):
                            p = part.strip()
                            if not p:
                                continue
                            try:
                                vals.add(datetime.strptime(p, "%Y-%m-%d").date())
                            except Exception:
                                continue
                        return vals

                    def _serialize_dates(values: set[date]) -> str:
                        return ";".join(sorted(d.isoformat() for d in values))

                    current_unavail = _parse_date_list(drow.get("unavailable_dates",""))
                    current_avail = _parse_date_list(drow.get("available_dates",""))
                    # home_dates kan ontbreken; vang dat af
                    current_home = _parse_date_list(drow.get("home_dates",""))
                    mode = st.radio("Kalender modus", ["Onbeschikbaar", "Beschikbaar (uitzondering)", "Thuiswerk"], horizontal=True, key=f"cal_mode_{did}")
                    is_unavail_mode = mode.startswith("Onbeschik")
                    is_avail_mode = mode.startswith("Beschikbaar")
                    is_home_mode = mode.startswith("Thuis")
                    pick_month = st.date_input("Kies maand", value=date.today().replace(day=1), key=f"unav_month_{did}")
                    month_start = date(pick_month.year, pick_month.month, 1)
                    # bepaal alle dagen van de maand
                    if pick_month.month == 12:
                        next_month = date(pick_month.year + 1, 1, 1)
                    else:
                        next_month = date(pick_month.year, pick_month.month + 1, 1)
                    days = []
                    dcur = month_start
                    while dcur < next_month:
                        days.append(dcur)
                        dcur = dcur + timedelta(days=1)

                    # render grid: 7 kolommen (ma..zo) met gekleurde tegels
                    st.caption("Legenda: 🟥 onbeschikbaar  🟩 beschikbaar  🟦 thuiswerk  ⬜ geen")
                    weekday_labels = ["ma","di","wo","do","vr","za","zo"]
                    cols = st.columns(7)
                    for idx, label in enumerate(weekday_labels):
                        cols[idx].markdown(f"**{label.upper()}**")

                    # vaste werkdagen van de arts om standaard groen te tonen
                    wd_series2 = state.dfs["doctor_workdays"][state.dfs["doctor_workdays"]["doctor_id"].astype(str).str.strip() == did]["weekday"]
                    person_wd = set([v for v in (_wd_to_int(x) for x in wd_series2.tolist()) if v is not None])

                    first_wd = (month_start.weekday() + 1)  # Monday=0 -> 1..7
                    from math import ceil
                    total_slots = ((first_wd - 1) + len(days))
                    total_rows = ceil(total_slots / 7)
                    index = 0
                    toggled_clicked = False
                    for r in range(total_rows):
                        cols_r = st.columns(7)
                        for c in range(7):
                            slot = r * 7 + c
                            if slot < (first_wd - 1) or index >= len(days):
                                cols_r[c].markdown(" ")
                            else:
                                dte = days[index]
                                index += 1
                                # Bepaal ico op basis van setjes en vaste werkdagen
                                if dte in current_unavail:
                                    ico = "🟥"
                                elif dte in current_home:
                                    ico = "🟦"
                                else:
                                    wd_num = int(dte.weekday()) + 1
                                    if dte in current_avail or wd_num in person_wd:
                                        ico = "🟩"
                                    else:
                                        ico = "⬜"
                                key = f"daybtn_{did}_{dte.isoformat()}"
                                if cols_r[c].button(f"{ico} {dte.day:02d}", key=key):
                                    toggled_clicked = True
                                    # Toggle volgens modus
                                    if is_unavail_mode:
                                        if dte in current_unavail:
                                            current_unavail.remove(dte)
                                        else:
                                            current_unavail.add(dte)
                                            # rood overschrijft anderen
                                            current_avail.discard(dte)
                                            current_home.discard(dte)
                                    elif is_avail_mode:
                                        if dte in current_avail:
                                            current_avail.remove(dte)
                                        else:
                                            current_avail.add(dte)
                                            current_unavail.discard(dte)
                                    elif is_home_mode:
                                        if dte in current_home:
                                            current_home.remove(dte)
                                        else:
                                            current_home.add(dte)
                                            current_unavail.discard(dte)
                    # Sla directe toggles meteen op en herlaad, zodat kleur direct ververst
                    if toggled_clicked:
                        docs2 = state.dfs["doctors"].copy()
                        idxs = docs2.index[docs2["doctor_id"].astype(str).str.strip() == did].tolist()
                        if idxs:
                            i = idxs[0]
                            docs2.at[i, "unavailable_dates"] = ";".join(sorted(d.isoformat() for d in current_unavail))
                            docs2.at[i, "available_dates"] = ";".join(sorted(d.isoformat() for d in current_avail))
                            if "home_dates" in docs2.columns:
                                docs2.at[i, "home_dates"] = ";".join(sorted(d.isoformat() for d in current_home))
                            state.dfs["doctors"] = docs2
                            _autosave()
                            st.experimental_rerun()

                    act1, act2, act3, act4 = st.columns(4)
                    with act1:
                        if st.button("Selecteer werkdagen", key=f"sel_wd_{did}"):
                            base_set = current_unavail if is_unavail_mode else current_avail
                            month_set = {d for d in base_set if not (d.year == month_start.year and d.month == month_start.month)}
                            for dte in days:
                                if dte.weekday() < 5:  # ma-vr
                                    month_set.add(dte)
                            docs2 = state.dfs["doctors"].copy()
                            idxs = docs2.index[docs2["doctor_id"].astype(str).str.strip() == did].tolist()
                            if idxs:
                                i = idxs[0]
                                col = "unavailable_dates" if is_unavail_mode else "available_dates"
                                docs2.at[i, col] = _serialize_dates(month_set)
                                state.dfs["doctors"] = docs2
                                _autosave()
                                st.success("Werkdagen geselecteerd voor deze maand.")
                    with act2:
                        if st.button("Wis maand", key=f"clear_month_{did}"):
                            base_set = current_unavail if is_unavail_mode else current_avail
                            month_set = {d for d in base_set if not (d.year == month_start.year and d.month == month_start.month)}
                            docs2 = state.dfs["doctors"].copy()
                            idxs = docs2.index[docs2["doctor_id"].astype(str).str.strip() == did].tolist()
                            if idxs:
                                i = idxs[0]
                                col = "unavailable_dates" if is_unavail_mode else "available_dates"
                                docs2.at[i, col] = _serialize_dates(month_set)
                                state.dfs["doctors"] = docs2
                                _autosave()
                                st.success("Maand gewist.")
                    with act3:
                        vac_start = st.date_input("2 weken vanaf", value=month_start, key=f"vac2_start_{did}")
                        if st.button("Markeer 2 weken", key=f"vac2_btn_{did}"):
                            new_set = set(current_unavail if is_unavail_mode else current_avail)
                            for i in range(14):
                                new_set.add(vac_start + timedelta(days=i))
                            docs2 = state.dfs["doctors"].copy()
                            idxs = docs2.index[docs2["doctor_id"].astype(str).str.strip() == did].tolist()
                            if idxs:
                                i = idxs[0]
                                col = "unavailable_dates" if is_unavail_mode else "available_dates"
                                docs2.at[i, col] = _serialize_dates(new_set)
                                state.dfs["doctors"] = docs2
                                _autosave()
                                st.success("2 weken vakantie gemarkeerd.")
                    with act4:
                        r1 = st.date_input("Bereik van", value=month_start, key=f"rng_from_{did}")
                        r2 = st.date_input("t/m", value=month_start + timedelta(days=6), key=f"rng_to_{did}")
                        if st.button("Markeer bereik", key=f"rng_mark_{did}"):
                            new_set = set(current_unavail if is_unavail_mode else current_avail)
                            dcur = r1
                            while dcur <= r2:
                                new_set.add(dcur)
                                dcur = dcur + timedelta(days=1)
                            docs2 = state.dfs["doctors"].copy()
                            idxs = docs2.index[docs2["doctor_id"].astype(str).str.strip() == did].tolist()
                            if idxs:
                                i = idxs[0]
                                col = "unavailable_dates" if is_unavail_mode else "available_dates"
                                docs2.at[i, col] = _serialize_dates(new_set)
                                state.dfs["doctors"] = docs2
                                _autosave()
                                st.success("Bereik gemarkeerd.")
                        if st.button("Wis bereik", key=f"rng_clear_{did}"):
                            new_set = set(current_unavail if is_unavail_mode else current_avail)
                            dcur = r1
                            while dcur <= r2:
                                if dcur in new_set:
                                    new_set.remove(dcur)
                                dcur = dcur + timedelta(days=1)
                            docs2 = state.dfs["doctors"].copy()
                            idxs = docs2.index[docs2["doctor_id"].astype(str).str.strip() == did].tolist()
                            if idxs:
                                i = idxs[0]
                                col = "unavailable_dates" if is_unavail_mode else "available_dates"
                                docs2.at[i, col] = _serialize_dates(new_set)
                                state.dfs["doctors"] = docs2
                                _autosave()
                                st.success("Bereik gewist.")

                    # Jaar-acties voor beschikbaarheid (per persoon)
                    st.caption("Jaaracties")
                    year = st.number_input("Jaar", min_value=2000, max_value=2100, value=date.today().year, step=1, key=f"year_{did}")
                    scope = st.radio("Dagen", ["Vaste werkdagen", "Alle dagen"], horizontal=True, key=f"year_scope_{did}")
                    if st.button("Zet beschikbaar in jaar", key=f"year_set_avail_{did}"):
                        # Alleen in beschikbaarheidsmodus heeft dit effect
                        base_set = set(current_avail)
                        # bepaal alle datums in jaar
                        start = date(int(year), 1, 1)
                        end = date(int(year), 12, 31)
                        dcur = start
                        wd_set = state.dfs["doctor_workdays"]
                        wd_series2 = wd_set[wd_set["doctor_id"].astype(str).str.strip() == did]["weekday"]
                        person_wd = set([v for v in (_wd_to_int(x) for x in wd_series2.tolist()) if v is not None])
                        while dcur <= end:
                            ok = True
                            if scope.startswith("Vaste"):
                                # alleen vaste werkdagen aanzetten
                                w = int(dcur.weekday()) + 1
                                ok = (w in person_wd)
                            if ok:
                                base_set.add(dcur)
                            dcur = dcur + timedelta(days=1)
                        docs2 = state.dfs["doctors"].copy()
                        idxs = docs2.index[docs2["doctor_id"].astype(str).str.strip() == did].tolist()
                        if idxs:
                            i = idxs[0]
                            docs2.at[i, "available_dates"] = ";".join(sorted(d.isoformat() for d in base_set))
                            state.dfs["doctors"] = docs2
                            _autosave()
                            st.success("Jaar-beschikbaarheid gezet.")
                    if st.button("Wis beschikbaar in jaar", key=f"year_clear_avail_{did}"):
                        base_set = set(current_avail)
                        start = date(int(year), 1, 1)
                        end = date(int(year), 12, 31)
                        dcur = start
                        while dcur <= end:
                            if dcur in base_set:
                                base_set.remove(dcur)
                            dcur = dcur + timedelta(days=1)
                        docs2 = state.dfs["doctors"].copy()
                        idxs = docs2.index[docs2["doctor_id"].astype(str).str.strip() == did].tolist()
                        if idxs:
                            i = idxs[0]
                            docs2.at[i, "available_dates"] = ";".join(sorted(d.isoformat() for d in base_set))
                            state.dfs["doctors"] = docs2
                            _autosave()
                            st.success("Jaar-beschikbaarheid gewist.")

                    # Opslaan-knop is niet meer nodig; clicks slaan direct op

    # Werkdagen artsen (in dezelfde tab)
    st.markdown("---")
    st.markdown("Werkdagen artsen")
    left2, right2 = st.columns([1,2])
    with left2:
        st.caption("Bulk import werkdagen (CSV/XLSX)")
        with st.popover("❓ Uitleg werkdagen"):
            st.markdown(
                "- Kolommen: `doctor_id,weekday` (1=ma, ..., 7=zo of `ma,di,wo,do,vr,za,zo`)\n"
                "- Voorbeeld: D10,1"
            )
        st.download_button(
            "Template CSV - doctor_workdays",
            data=_csv_template(
                ["doctor_id","weekday"],
                [["D10","ma"]]
            ),
            file_name="doctor_workdays_template.csv",
            mime="text/csv"
        )
        up_wd = st.file_uploader("Bestand werkdagen", type=["csv","xlsx"], key="bulk_wd_file_v2")
        wd_overwrite_all = st.checkbox("Bestaande werkdagen overschrijven voor dokters in bestand", value=False, key="bulk_wd_overwrite_v2")
        if st.button("Importeer werkdagen", disabled=up_wd is None, key="btn_import_wd_v2"):
            try:
                if up_wd.name.lower().endswith(".xlsx"):
                    df_new = pd.read_excel(up_wd, dtype=str).fillna("")
                else:
                    df_new = pd.read_csv(up_wd, dtype=str).fillna("")
                req = ["doctor_id","weekday"]
                miss = [c for c in req if c not in df_new.columns]
                if miss:
                    raise ValueError(f"Ontbrekende kolommen: {miss}")
                # normaliseer weekday
                df_new["weekday"] = df_new["weekday"].apply(lambda v: _wd_to_int(v))
                df_new = df_new.dropna(subset=["weekday"])
                wd_df = state.dfs["doctor_workdays"].copy()
                if wd_overwrite_all:
                    to_clear = set(df_new["doctor_id"].astype(str).str.strip())
                    wd_df = wd_df[~wd_df["doctor_id"].astype(str).str.strip().isin(to_clear)]
                merged = pd.concat([wd_df, df_new[req]], ignore_index=True)
                merged = merged.drop_duplicates(subset=["doctor_id","weekday"], keep="last")
                state.dfs["doctor_workdays"] = merged
                st.success(f"Werkdagen geïmporteerd: {len(df_new)} rijen.")
                _autosave()
            except Exception as e:
                st.error(f"Import werkdagen mislukt: {e}")
    with right2:
        st.markdown("Bewerk werkdagen per arts")
        docs_df = state.dfs["doctors"].copy()
        wd_df = state.dfs["doctor_workdays"].copy()
        for _, drow in docs_df.sort_values(["name", "doctor_id"]).iterrows():
            did = str(drow["doctor_id"]).strip()
            dname = str(drow["name"]).strip() or did
            rows = wd_df[wd_df["doctor_id"].astype(str).str.strip() == did]["weekday"].tolist()
            curr_wd = set([v for v in (_wd_to_int(x) for x in rows) if v is not None])
            with st.expander(f"{dname} ({did})", expanded=False):
                st.caption("Wijzig werkdagen")
                cc1, cc2, cc3, cc4, cc5, cc6, cc7 = st.columns(7)
                with cc1: ma2 = st.checkbox("ma", value=(1 in curr_wd), key=f"edit_wd2_{did}_1")
                with cc2: di2 = st.checkbox("di", value=(2 in curr_wd), key=f"edit_wd2_{did}_2")
                with cc3: wo2 = st.checkbox("wo", value=(3 in curr_wd), key=f"edit_wd2_{did}_3")
                with cc4: do2 = st.checkbox("do", value=(4 in curr_wd), key=f"edit_wd2_{did}_4")
                with cc5: vr2 = st.checkbox("vr", value=(5 in curr_wd), key=f"edit_wd2_{did}_5")
                with cc6: za2 = st.checkbox("za", value=(6 in curr_wd), key=f"edit_wd2_{did}_6")
                with cc7: zo2 = st.checkbox("zo", value=(7 in curr_wd), key=f"edit_wd2_{did}_7")
                if st.button("Opslaan werkdagen", key=f"save_wd2_{did}"):
                    new_set = set()
                    if ma2: new_set.add(1)
                    if di2: new_set.add(2)
                    if wo2: new_set.add(3)
                    if do2: new_set.add(4)
                    if vr2: new_set.add(5)
                    if za2: new_set.add(6)
                    if zo2: new_set.add(7)
                    wd_df2 = state.dfs["doctor_workdays"].copy()
                    wd_df2 = wd_df2[wd_df2["doctor_id"].astype(str).str.strip() != did]
                    for d in sorted(new_set):
                        wd_df2.loc[len(wd_df2)] = [did, d]
                    state.dfs["doctor_workdays"] = wd_df2
                    _autosave()
                    st.success("Werkdagen opgeslagen.")

st.subheader("Opslaan/Exporteren")
col_save1, col_save2 = st.columns(2)
with col_save1:
    if st.button("Opslaan naar CSV's (data/custom)"):
        out_dir = Path("data/custom")
        out_dir.mkdir(parents=True, exist_ok=True)
        name_map = {
            "doctors": "doctors.csv",
            "locations": "locations.csv",
            "rooms": "rooms.csv",
            "sessions": "sessions.csv",
            "preferences": "preferences.csv",
            "travel_times": "travel_times.csv",
            "doctor_workdays": "doctor_workdays.csv",
            "doctor_week_rules": "doctor_week_rules.csv",
        }
        for k, fname in name_map.items():
            state.dfs[k].to_csv(out_dir / fname, index=False)
        st.success(f"Opgeslagen naar map: {out_dir}")
with col_save2:
    if st.button("Opslaan als Excel (data/custom/megaplanner_data.xlsx)"):
        out_dir = Path("data/custom")
        out_dir.mkdir(parents=True, exist_ok=True)
        xlsx_path = out_dir / "megaplanner_data.xlsx"
        with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
            state.dfs["doctors"].to_excel(writer, index=False, sheet_name="Doctors")
            state.dfs["locations"].to_excel(writer, index=False, sheet_name="Locations")
            state.dfs["rooms"].to_excel(writer, index=False, sheet_name="Rooms")
            state.dfs["sessions"].to_excel(writer, index=False, sheet_name="Sessions")
            state.dfs["preferences"].to_excel(writer, index=False, sheet_name="Preferences")
            state.dfs["travel_times"].to_excel(writer, index=False, sheet_name="TravelTimes")
            state.dfs["doctor_workdays"].to_excel(writer, index=False, sheet_name="DoctorWorkdays")
            state.dfs["doctor_week_rules"].to_excel(writer, index=False, sheet_name="DoctorWeekRules")
        st.success(f"Excel opgeslagen: {xlsx_path}")
        # Geef ook directe download
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            state.dfs["doctors"].to_excel(writer, index=False, sheet_name="Doctors")
            state.dfs["locations"].to_excel(writer, index=False, sheet_name="Locations")
            state.dfs["rooms"].to_excel(writer, index=False, sheet_name="Rooms")
            state.dfs["sessions"].to_excel(writer, index=False, sheet_name="Sessions")
            state.dfs["preferences"].to_excel(writer, index=False, sheet_name="Preferences")
            state.dfs["travel_times"].to_excel(writer, index=False, sheet_name="TravelTimes")
            state.dfs["doctor_workdays"].to_excel(writer, index=False, sheet_name="DoctorWorkdays")
            state.dfs["doctor_week_rules"].to_excel(writer, index=False, sheet_name="DoctorWeekRules")
        st.download_button("Download Excel nu", data=buf.getvalue(), file_name="megaplanner_data.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


st.subheader("Optioneel: Genereer sessies op basis van weekregels")
col1, col2, col3 = st.columns(3)
with col1:
    gen_start = st.date_input("Vanaf datum", value=date(date.today().year, date.today().month, 1))
with col2:
    gen_end_default = date(date.today().year, 12, 31)
    gen_end = st.date_input("Tot en met", value=gen_end_default)
with col3:
    default_start_time = st.text_input("Sessiestart (HH:MM)", value="09:00")
    default_end_time = st.text_input("Sessie-einde (HH:MM)", value="17:00")

def _weekday1_7(d: date) -> int:
    return int(datetime(d.year, d.month, d.day).weekday()) + 1

def _week_of_month1_5(d: date) -> int:
    return (int(d.day) - 1) // 7 + 1

def _parse_hhmm(txt: str) -> Tuple[int, int]:
    hh, mm = txt.split(":")
    return int(hh), int(mm)

def generate_sessions_from_rules(df_locations: pd.DataFrame, df_week_rules: pd.DataFrame, start: date, end: date, start_hhmm: str, end_hhmm: str) -> pd.DataFrame:
    # Bepaal per datum de set locaties die in weekregels voorkomen
    loc_ids = set(df_locations["location_id"].astype(str).str.strip().tolist())
    loc_time_map = {
        str(r["location_id"]).strip(): (
            str(r.get("default_start_time", "")).strip(),
            str(r.get("default_end_time", "")).strip(),
        )
        for _, r in df_locations.iterrows()
    }
    # Map rooms per locatie (eerste kamer wordt automatisch gekozen indien uniek)
    room_map: Dict[str, List[str]] = {}
    if "rooms" in state.dfs:
        for _, r in state.dfs["rooms"].iterrows():
            lid = str(r["location_id"]).strip()
            rn = str(r["name"]).strip()
            if lid and rn:
                room_map.setdefault(lid, []).append(rn)
    out_rows: List[Dict[str, str]] = []
    existing_ids: Set[str] = set()
    sh, sm = _parse_hhmm(start_hhmm)
    eh, em = _parse_hhmm(end_hhmm)
    curr = start
    while curr <= end:
        wom = _week_of_month1_5(curr)
        wd = _weekday1_7(curr)
        # alle regels die overeenkomen
        matching = df_week_rules[
            (df_week_rules["week_of_month"].astype(str).str.strip() == str(wom)) &
            (df_week_rules["weekday"].astype(str).str.lower().isin([str(wd), "ma" if wd==1 else "di" if wd==2 else "wo" if wd==3 else "do" if wd==4 else "vr" if wd==5 else "za" if wd==6 else "zo"]))
        ]
        day_locations = set(matching["location_id"].astype(str).str.strip().tolist())
        # filter op bekende locaties
        day_locations = {loc for loc in day_locations if loc in loc_ids}
        for loc in sorted(day_locations):
            session_id = f"GEN-{curr.strftime('%Y%m%d')}-{loc}"
            if session_id in existing_ids:
                # als al bestaat, maak suffix
                k = 2
                while f"{session_id}-{k}" in existing_ids:
                    k += 1
                session_id = f"{session_id}-{k}"
            existing_ids.add(session_id)
            # kies per locatie default tijden als aanwezig
            loc_start, loc_end = loc_time_map.get(loc, ("", ""))
            use_start = loc_start if loc_start else f"{sh:02d}:{sm:02d}"
            use_end = loc_end if loc_end else f"{eh:02d}:{em:02d}"
            # Kies kamer: indien precies 1 kamer voor locatie, gebruik die, anders leeg
            auto_room = ""
            rooms_for_loc = room_map.get(loc, [])
            if len(rooms_for_loc) == 1:
                auto_room = rooms_for_loc[0]
            out_rows.append({
                "session_id": session_id,
                "date": curr.isoformat(),
                "location_id": loc,
                "start_time": use_start,
                "end_time": use_end,
                "required_skill": "",
                "room": auto_room,
            })
        curr += timedelta(days=1)
    return pd.DataFrame(out_rows, columns=["session_id","date","location_id","start_time","end_time","required_skill","room"])

if st.button("Genereer sessies (voegt toe aan Sessions)"):
    gen_df = generate_sessions_from_rules(state.dfs["locations"], state.dfs["doctor_week_rules"], gen_start, gen_end, default_start_time, default_end_time)
    if len(gen_df) == 0:
        st.warning("Geen sessies gegenereerd; controleer weekregels en periode.")
    else:
        # concat en deduplicate op session_id
        merged = pd.concat([state.dfs["sessions"], gen_df], ignore_index=True)
        merged = merged.drop_duplicates(subset=["session_id"], keep="last")
        state.dfs["sessions"] = merged
        st.success(f"{len(gen_df)} sessies toegevoegd.")


st.subheader("Plannen")
if st.button("Maak planning"):
    # Schrijf naar tijdelijke buffers en gebruik bestaande readers (valideren formats)
    def df_to_csv_bytes(df: pd.DataFrame) -> io.BytesIO:
        buf = io.BytesIO()
        df.to_csv(buf, index=False)
        buf.seek(0)
        return buf

    doctors = read_doctors(df_to_csv_bytes(state.dfs["doctors"]))
    locations = read_locations(df_to_csv_bytes(state.dfs["locations"]))
    sessions = read_sessions(df_to_csv_bytes(state.dfs["sessions"]))
    preferences = read_preferences(df_to_csv_bytes(state.dfs["preferences"]))
    travel_times = read_travel_times(df_to_csv_bytes(state.dfs["travel_times"])) if len(state.dfs["travel_times"]) > 0 else {}
    workdays = read_doctor_workdays(df_to_csv_bytes(state.dfs["doctor_workdays"])) if len(state.dfs["doctor_workdays"]) > 0 else {}
    week_rules = read_doctor_week_rules(df_to_csv_bytes(state.dfs["doctor_week_rules"])) if len(state.dfs["doctor_week_rules"]) > 0 else []

    try:
        assignments, objective = solve_schedule(doctors, locations, sessions, preferences, travel_times, workdays, week_rules)
    except Exception as e:
        st.error(f"Planner fout: {e}")
    else:
        st.success(f"Planning gereed. Totale voorkeursscore: {objective}")
        # Toon resultaat
        rows = []
        for sess_id, doc_id in assignments.items():
            s = sessions[sess_id]
            d = doctors[doc_id]
            rows.append({
                "date": s.date.isoformat(),
                "session_id": s.session_id,
                "location_id": s.location_id,
                "doctor_id": d.doctor_id,
                "doctor_name": d.name,
                "start_time": s.start_time.strftime("%H:%M"),
                "end_time": s.end_time.strftime("%H:%M"),
                "room": getattr(s, "room", ""),
                "required_skill": s.required_skill or "",
            })
        result_df = pd.DataFrame(rows).sort_values(["date", "location_id", "start_time"])
        st.dataframe(result_df, use_container_width=True)
        # Bewaar in state voor Agenda
        state.schedule_df = result_df.copy()
        # Schrijf ook naar schijf voor latere sessies
        try:
            write_schedule_csv(Path("output/schedule.csv"), assignments, doctors, locations, sessions)
        except Exception:
            pass

        # Downloads
        csv_buf = io.StringIO()
        result_df.to_csv(csv_buf, index=False)
        st.download_button("Download CSV", data=csv_buf.getvalue(), file_name="schedule.csv", mime="text/csv")

        xlsx_buf = io.BytesIO()
        with pd.ExcelWriter(xlsx_buf, engine="openpyxl") as writer:
            result_df.to_excel(writer, index=False, sheet_name="Schedule")
            # optioneel: ook data meegeven
            state.dfs["doctors"].to_excel(writer, index=False, sheet_name="Doctors")
            state.dfs["locations"].to_excel(writer, index=False, sheet_name="Locations")
            state.dfs["sessions"].to_excel(writer, index=False, sheet_name="Sessions")
            state.dfs["preferences"].to_excel(writer, index=False, sheet_name="Preferences")
            state.dfs["travel_times"].to_excel(writer, index=False, sheet_name="TravelTimes")
            state.dfs["doctor_workdays"].to_excel(writer, index=False, sheet_name="DoctorWorkdays")
            state.dfs["doctor_week_rules"].to_excel(writer, index=False, sheet_name="DoctorWeekRules")
        st.download_button("Download Excel", data=xlsx_buf.getvalue(), file_name="schedule.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

st.divider()
st.caption("Tip: gebruik weekregels en vaste werkdagen om snel sessies voor de rest van het jaar te genereren en met één klik te plannen.")

st.subheader("Snel plannen")
colA, colB, colC = st.columns(3)
with colA:
    plan_end = st.date_input("Plan t/m datum", value=date(date.today().year, 12, 31), key="plan_end_input")
with colB:
    if st.button("Plan t/m datum (genereer + plan)"):
        gen_df = generate_sessions_from_rules(state.dfs["locations"], state.dfs["doctor_week_rules"], date.today(), plan_end, default_start_time, default_end_time)
        merged = pd.concat([state.dfs["sessions"], gen_df], ignore_index=True).drop_duplicates(subset=["session_id"], keep="last")
        state.dfs["sessions"] = merged
        # run planning
        try:
            def df_to_csv_bytes(df: pd.DataFrame) -> io.BytesIO:
                buf = io.BytesIO()
                df.to_csv(buf, index=False)
                buf.seek(0)
                return buf
            doctors = read_doctors(df_to_csv_bytes(state.dfs["doctors"]))
            locations = read_locations(df_to_csv_bytes(state.dfs["locations"]))
            sessions = read_sessions(df_to_csv_bytes(state.dfs["sessions"]))
            preferences = read_preferences(df_to_csv_bytes(state.dfs["preferences"]))
            travel_times = read_travel_times(df_to_csv_bytes(state.dfs["travel_times"])) if len(state.dfs["travel_times"]) > 0 else {}
            workdays = read_doctor_workdays(df_to_csv_bytes(state.dfs["doctor_workdays"])) if len(state.dfs["doctor_workdays"]) > 0 else {}
            week_rules = read_doctor_week_rules(df_to_csv_bytes(state.dfs["doctor_week_rules"])) if len(state.dfs["doctor_week_rules"]) > 0 else []
            assignments, objective = solve_schedule(doctors, locations, sessions, preferences, travel_times, workdays, week_rules)
        except Exception as e:
            st.error(f"Planner fout: {e}")
        else:
            st.success(f"Planning gereed t/m {plan_end.isoformat()}. Totale voorkeursscore: {objective}")
    with colC:
        if st.button("Plan t/m einde jaar (genereer + plan)"):
            end_of_year = date(date.today().year, 12, 31)
            st.session_state["plan_end_input"] = end_of_year
            st.experimental_rerun()

st.subheader("Controleer data")
if st.button("Controleer data (validatie)"):
    errors: List[Dict[str, str]] = []

    def is_hhmm(s: str) -> bool:
        try:
            _ = datetime.strptime(s, "%H:%M")
            return True
        except Exception:
            return False

    # Doctors
    doc_ids = set()
    for idx, r in state.dfs["doctors"].iterrows():
        did = str(r["doctor_id"]).strip()
        if not did:
            errors.append({"table": "doctors", "row": str(idx), "error": "doctor_id ontbreekt"})
        elif did in doc_ids:
            errors.append({"table": "doctors", "row": str(idx), "error": f"doctor_id dubbel: {did}"})
        doc_ids.add(did)
        ms = str(r["max_sessions"]).strip()
        if ms and not ms.isdigit():
            errors.append({"table": "doctors", "row": str(idx), "error": "max_sessions moet geheel getal zijn"})

    # Locations
    loc_ids = set()
    for idx, r in state.dfs["locations"].iterrows():
        lid = str(r["location_id"]).strip()
        if not lid:
            errors.append({"table": "locations", "row": str(idx), "error": "location_id ontbreekt"})
        elif lid in loc_ids:
            errors.append({"table": "locations", "row": str(idx), "error": f"location_id dubbel: {lid}"})
        loc_ids.add(lid)
        dst = str(r.get("default_start_time", "")).strip()
        det = str(r.get("default_end_time", "")).strip()
        if dst and not is_hhmm(dst):
            errors.append({"table": "locations", "row": str(idx), "error": "default_start_time geen HH:MM"})
        if det and not is_hhmm(det):
            errors.append({"table": "locations", "row": str(idx), "error": "default_end_time geen HH:MM"})

    # Sessions
    sess_ids = set()
    for idx, r in state.dfs["sessions"].iterrows():
        sid = str(r["session_id"]).strip()
        if not sid:
            errors.append({"table": "sessions", "row": str(idx), "error": "session_id ontbreekt"})
        elif sid in sess_ids:
            errors.append({"table": "sessions", "row": str(idx), "error": f"session_id dubbel: {sid}"})
        sess_ids.add(sid)
        try:
            _ = datetime.strptime(str(r["date"]).strip(), "%Y-%m-%d")
        except Exception:
            errors.append({"table": "sessions", "row": str(idx), "error": "date geen YYYY-MM-DD"})
        stime = str(r["start_time"]).strip()
        etime = str(r["end_time"]).strip()
        if not is_hhmm(stime):
            errors.append({"table": "sessions", "row": str(idx), "error": "start_time geen HH:MM"})
        if not is_hhmm(etime):
            errors.append({"table": "sessions", "row": str(idx), "error": "end_time geen HH:MM"})

    # Preferences
    for idx, r in state.dfs["preferences"].iterrows():
        did = str(r["doctor_id"]).strip()
        lid = str(r["location_id"]).strip()
        sc = str(r["score"]).strip()
        if did and did not in doc_ids:
            errors.append({"table": "preferences", "row": str(idx), "error": f"doctor_id onbekend: {did}"})
        if lid and lid not in loc_ids:
            errors.append({"table": "preferences", "row": str(idx), "error": f"location_id onbekend: {lid}"})
        if sc and not (sc.lstrip("-").isdigit()):
            errors.append({"table": "preferences", "row": str(idx), "error": "score geen geheel getal"})

    # Travel times
    for idx, r in state.dfs["travel_times"].iterrows():
        a = str(r["from_location_id"]).strip()
        b = str(r["to_location_id"]).strip()
        m = str(r["minutes"]).strip()
        if a and a not in loc_ids:
            errors.append({"table": "travel_times", "row": str(idx), "error": f"from_location_id onbekend: {a}"})
        if b and b not in loc_ids:
            errors.append({"table": "travel_times", "row": str(idx), "error": f"to_location_id onbekend: {b}"})
        if m and not m.isdigit():
            errors.append({"table": "travel_times", "row": str(idx), "error": "minutes geen geheel getal"})

    # DoctorWorkdays
    valid_wd = {"1","2","3","4","5","6","7","ma","di","wo","do","vr","za","zo"}
    for idx, r in state.dfs["doctor_workdays"].iterrows():
        did = str(r["doctor_id"]).strip()
        wd = str(r["weekday"]).strip().lower()
        if did and did not in doc_ids:
            errors.append({"table": "doctor_workdays", "row": str(idx), "error": f"doctor_id onbekend: {did}"})
        if wd and wd not in valid_wd:
            errors.append({"table": "doctor_workdays", "row": str(idx), "error": f"weekday ongeldig: {wd}"})

    # DoctorWeekRules
    for idx, r in state.dfs["doctor_week_rules"].iterrows():
        did = str(r["doctor_id"]).strip()
        wom = str(r["week_of_month"]).strip()
        wd = str(r["weekday"]).strip().lower()
        lid = str(r["location_id"]).strip()
        if did and did not in doc_ids:
            errors.append({"table": "doctor_week_rules", "row": str(idx), "error": f"doctor_id onbekend: {did}"})
        if lid and lid not in loc_ids:
            errors.append({"table": "doctor_week_rules", "row": str(idx), "error": f"location_id onbekend: {lid}"})
        if wom and (not wom.isdigit() or int(wom) < 1 or int(wom) > 5):
            errors.append({"table": "doctor_week_rules", "row": str(idx), "error": "week_of_month niet 1..5"})
        if wd and wd not in valid_wd:
            errors.append({"table": "doctor_week_rules", "row": str(idx), "error": f"weekday ongeldig: {wd}"})

    if errors:
        st.error(f"{len(errors)} validatiefouten gevonden.")
        st.dataframe(pd.DataFrame(errors), use_container_width=True)
    else:
        st.success("Geen fouten gevonden.")

# Agenda (planningsoverzicht)
if mode == "Agenda (planning)":
    st.subheader("Agenda (planningsoverzicht)")
    # Probeer bestaande planning te laden uit state of uit output/schedule.csv
    if "schedule_df" not in state:
        out_csv = Path("output/schedule.csv")
        if out_csv.exists():
            try:
                state.schedule_df = pd.read_csv(out_csv, dtype=str).fillna("")
            except Exception:
                pass
    if "schedule_df" not in state or len(state.schedule_df) == 0:
        st.info("Nog geen planning beschikbaar. Maak eerst een planning of importeer `output/schedule.csv`.")
    else:
        sched = state.schedule_df.copy()
        # Parseer datums voor filtering
        sched["date"] = pd.to_datetime(sched["date"], errors="coerce").dt.date
        # Filters
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            start_d = st.date_input("Vanaf", value=min(sched["date"]))
        with c2:
            end_d = st.date_input("Tot en met", value=max(sched["date"]))
        with c3:
            doc_options = sorted(sched["doctor_name"].unique().tolist())
            sel_docs = st.multiselect("Artsen", options=doc_options, default=doc_options)
        with c4:
            loc_options = sorted(sched["location_id"].unique().tolist())
            sel_locs = st.multiselect("Locaties", options=loc_options, default=loc_options)
        mask = (sched["date"] >= start_d) & (sched["date"] <= end_d) & sched["doctor_name"].isin(sel_docs) & sched["location_id"].isin(sel_locs)
        view = sched.loc[mask].copy()
        if len(view) == 0:
            st.warning("Geen afspraken in dit bereik.")
        else:
            t1, t2 = st.tabs(["Per dag", "Per arts"])
            with t1:
                day_groups = view.sort_values(["date", "start_time", "doctor_name"])
                for d, df_day in day_groups.groupby("date"):
                    st.markdown(f"### {d.isoformat()}")
                    st.dataframe(df_day[["start_time","end_time","doctor_name","location_id","room","session_id"]].reset_index(drop=True), use_container_width=True)
            with t2:
                # Per arts groeperen
                by_doc = view.sort_values(["doctor_name", "date", "start_time"])
                for dn, df_doc in by_doc.groupby("doctor_name"):
                    st.markdown(f"### {dn}")
                    st.dataframe(df_doc[["date","start_time","end_time","location_id","room","session_id"]].reset_index(drop=True), use_container_width=True)
            # Export van gefilterde view
            st.download_button("Download gefilterde agenda (CSV)", data=view.to_csv(index=False), file_name="agenda_filtered.csv", mime="text/csv")

