from __future__ import annotations

import re
from typing import Any, Mapping

Scalar = str | int | float | bool | None
US_SURVEY_FOOT_M = 1200.0 / 3937.0


def first(properties: Mapping[str, Any], *names: str, default=None):
    lowered = {str(key).lower(): value for key, value in properties.items()}
    for name in names:
        if name.lower() in lowered:
            return lowered[name.lower()]
    return default


def as_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return None


def as_bool_tag(value: Any) -> bool:
    return str(value or "").strip().lower() not in {"", "0", "false", "no", "none"}


def parse_dcm_width_m(value: Any) -> float | None:
    """DCM Streetwidth is textual and represents mapped width in feet."""
    if value is None:
        return None
    match = re.search(r"[-+]?\d+(?:\.\d+)?", str(value))
    if not match:
        return None
    return float(match.group(0)) * US_SURVEY_FOOT_M


def parse_osm_width_m(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip().lower()
    match = re.search(r"[-+]?\d+(?:\.\d+)?", text)
    if not match:
        return None
    number = float(match.group(0))
    if "ft" in text or "foot" in text or "feet" in text or "'" in text:
        return number * 0.3048
    return number


def scalar_properties(properties: Mapping[str, Any]) -> dict[str, Scalar]:
    return {
        str(key): value
        for key, value in properties.items()
        if isinstance(value, (str, int, float, bool)) or value is None
    }
