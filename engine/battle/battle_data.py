"""Battle content loaders (P17.1) — all army numbers as data.

Everything the resolver needs — unit archetypes, formations,
matchup RPS multipliers, terrain modifiers, fortification stats —
lives in data/battles/*.json and loads through here. No stats are
hardcoded in the engine (content-as-data rule).
"""

import json
import logging
from pathlib import Path

logger = logging.getLogger("llm_rpg.battle.data")

_ROOT = Path(__file__).resolve().parent.parent.parent / "data" / \
    "battles"


def _load(name: str) -> dict:
    try:
        return json.loads((_ROOT / name).read_text())
    except Exception as e:
        logger.warning(f"battle data {name} unreadable: {e}")
        return {}


UNITS = _load("units.json")
FORMATIONS = _load("formations.json")
FORTIFICATIONS = _load("fortifications.json")
_MATCH = _load("matchups.json")
MATCHUP = _MATCH.get("matchup", {})
TERRAIN = _MATCH.get("terrain", {})

DEFAULT_UNIT = "infantry_sword"


def unit_stats(unit_type: str) -> dict:
    return UNITS.get(unit_type, UNITS.get(DEFAULT_UNIT, {}))


def category_of(unit_type: str) -> str:
    return unit_stats(unit_type).get("category", "infantry")


def matchup_bonus(attacker_cat: str, defender_cat: str) -> float:
    return MATCHUP.get(f"{attacker_cat}|{defender_cat}", 1.0)


def terrain_mod(terrain: str) -> dict:
    return TERRAIN.get(terrain, TERRAIN.get("plains", {}))


def formation(name) -> dict:
    return FORMATIONS.get(name or "", {})


def fort_stats(fort_type: str) -> dict:
    return FORTIFICATIONS.get(fort_type, {"hp": 100, "defense_bonus": 1.0})
