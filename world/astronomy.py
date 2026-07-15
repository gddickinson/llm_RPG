"""Astronomy (P8.1, ported from autonomous_world) — the sky is real.

Solar-declination day length that varies by season (long summer days,
short winter ones at the realm's ~45°N latitude), dawn/dusk bands,
solar intensity for future crops/temperature — and TWO moons, silver
Lunara (28-day cycle) and copper Thal (47-day cycle), each with proper
phases. When both ride full together the realm calls it a Conjunction
(the cycles align only a handful of nights in ~4 years) — the nightly
stack turns it into an omen, and moonlight brightens clear nights in
the lighting system.

Pure functions throughout; constants live in `data/astronomy.json`
(sane in-code defaults if the file is missing). The year is the
calendar's 360 days (12 months of 30).
"""

import json
import logging
import math
import os
from typing import Dict, List, Tuple

logger = logging.getLogger("llm_rpg.astronomy")

YEAR_LENGTH = 360            # 12 months x 30 days (world/calendar.py)
SUMMER_SOLSTICE = 90         # day-of-year of the longest day

_DEFAULTS = {
    "axial_tilt": 23.5,
    "latitude": 45.0,
    "twilight_hours": 1.0,
    "conjunction_tolerance": 0.1,
    "moons": [
        {"name": "Lunara", "cycle": 28, "color": "silver"},
        {"name": "Thal", "cycle": 47, "color": "copper"},
    ],
}


def _config() -> Dict:
    global _CFG
    try:
        return _CFG
    except NameError:
        pass
    cfg = dict(_DEFAULTS)
    try:
        with open(os.path.join("data", "astronomy.json")) as fp:
            cfg.update(json.load(fp))
    except (OSError, json.JSONDecodeError):
        logger.info("astronomy.json missing/corrupt; using defaults")
    _CFG = cfg
    return cfg


# ---------------------------------------------------------------- sun

def solar_declination(day_of_year: int) -> float:
    cfg = _config()
    angle = 2 * math.pi * (day_of_year - SUMMER_SOLSTICE) / YEAR_LENGTH
    return cfg["axial_tilt"] * math.cos(angle)


def day_length(day_of_year: int, latitude: float = None) -> float:
    """Hours of daylight (0-24); handles polar day/night."""
    lat = _config()["latitude"] if latitude is None else latitude
    dec = math.radians(solar_declination(day_of_year))
    lat_r = math.radians(lat)
    cos_ha = -math.tan(lat_r) * math.tan(dec)
    if cos_ha < -1.0:
        return 24.0
    if cos_ha > 1.0:
        return 0.0
    return (2.0 * math.acos(cos_ha) / math.pi) * 12.0


def sunrise_sunset(day_of_year: int,
                   latitude: float = None) -> Tuple[float, float]:
    """(sunrise, sunset) as day fractions; 0.0 midnight, 0.5 noon."""
    hours = day_length(day_of_year, latitude)
    if hours >= 24.0:
        return (0.0, 1.0)
    if hours <= 0.0:
        return (0.5, 0.5)
    half = hours / 48.0
    return (0.5 - half, 0.5 + half)


def solar_intensity(day_of_year: int, latitude: float = None) -> float:
    """0-1 noon sun strength — future temperature/crop input."""
    lat = _config()["latitude"] if latitude is None else latitude
    elevation = 90 - abs(lat - solar_declination(day_of_year))
    return max(0.0, min(1.0, elevation / 90.0))


# --------------------------------------------------------------- moons

def moon_phase(day: int, cycle: int) -> float:
    """0.0 new -> 0.5 full -> 1.0 new again."""
    return (day % cycle) / cycle


def phase_name(phase: float) -> str:
    if phase < 0.06 or phase > 0.94:
        return "new"
    if phase < 0.19:
        return "waxing crescent"
    if phase < 0.31:
        return "first quarter"
    if phase < 0.44:
        return "waxing gibbous"
    if phase < 0.56:
        return "full"
    if phase < 0.69:
        return "waning gibbous"
    if phase < 0.81:
        return "last quarter"
    return "waning crescent"


def moons_tonight(day: int) -> List[Dict]:
    out = []
    for moon in _config()["moons"]:
        phase = moon_phase(day, moon["cycle"])
        out.append({"name": moon["name"], "color": moon["color"],
                    "phase": phase, "phase_name": phase_name(phase)})
    return out


def is_conjunction(day: int) -> bool:
    """Every moon near full on the same night — the omen night."""
    tol = _config()["conjunction_tolerance"]
    return all(abs(moon_phase(day, m["cycle"]) - 0.5) < tol
               for m in _config()["moons"])


def moonlight(day: int) -> float:
    """0-1 brightness of the night sky: the fullest moon dominates."""
    lights = [1.0 - 2.0 * abs(moon_phase(day, m["cycle"]) - 0.5)
              for m in _config()["moons"]]
    return max(lights) if lights else 0.0


def announce_conjunction(engine, day: int) -> bool:
    """Nightly-stack hook: make the omen night diegetic."""
    if not is_conjunction(day):
        return False
    names = " and ".join(m["name"] for m in _config()["moons"])
    note = (f"Conjunction: {names} ride full together — "
            f"an ill-omened sky.")
    engine.memory_manager.add_event(f"[Realm] {note}")
    try:
        engine.world_director.rumors.append(note)
        del engine.world_director.rumors[:-5]
    except Exception:
        pass
    return True


# ------------------------------------------------------------ summary

def get_astronomy(day: int, latitude: float = None) -> Dict:
    """Everything about the sky for a given absolute game day."""
    doy = day % YEAR_LENGTH
    rise, sset = sunrise_sunset(doy, latitude)
    return {
        "day_of_year": doy,
        "day_length_hours": day_length(doy, latitude),
        "sunrise": rise,
        "sunset": sset,
        "solar_intensity": solar_intensity(doy, latitude),
        "moons": moons_tonight(day),
        "conjunction": is_conjunction(day),
        "moonlight": moonlight(day),
    }
