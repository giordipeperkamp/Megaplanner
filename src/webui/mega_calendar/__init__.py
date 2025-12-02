import os
from typing import Any, Dict, List, Optional

import streamlit.components.v1 as components

_COMPONENT_NAME = "mega_calendar"
_FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "frontend", "build")

_calendar_component = components.declare_component(
    _COMPONENT_NAME,
    path=_FRONTEND_DIR,
)


def calendar(
    events: List[Dict[str, Any]] | None = None,
    options: Dict[str, Any] | None = None,
    custom_css: str = "",
    callbacks: List[str] | None = None,
    license_key: Optional[str] = None,
    meta: Optional[Dict[str, Any]] = None,
    key: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Streamlit wrapper voor de aangepaste FullCalendar-component.

    Parameters
    ----------
    events: lijst met FullCalendar events
    options: FullCalendar opties
    custom_css: extra CSS
    callbacks: lijst met callbacks die naar Streamlit gestuurd worden
    license_key: FullCalendar licentie (optioneel)
    meta: extra data voor popup (kamers, artsen, labels)
    key: Streamlit key
    """

    component_value = _calendar_component(
        events=events or [],
        options=options or {},
        custom_css=custom_css,
        callbacks=callbacks or ["dateClick", "eventClick", "eventChange", "eventsSet", "select", "selectSubmit"],
        license_key=license_key or "CC-Attribution-NonCommercial-NoDerivatives",
        meta=meta or {},
        key=key,
        default={},
    )
    return component_value or {}

