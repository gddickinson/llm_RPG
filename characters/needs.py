"""NPC needs simulation — hunger and fatigue.

Each NPC tracks `hunger` and `fatigue` in their `metadata` dict.
Both range 0 (satisfied) to 100 (critical). Needs grow over game time
and motivate schedule actions (eat, sleep).
"""

import logging
from typing import Any

logger = logging.getLogger("llm_rpg.needs")


HUNGER_PER_HOUR = 3      # +3 per game hour
FATIGUE_PER_HOUR = 2     # +2 per game hour while awake

HUNGER_HUNGRY = 60
HUNGER_STARVING = 90
FATIGUE_TIRED = 60
FATIGUE_EXHAUSTED = 90


def _ensure(npc) -> dict:
    meta = getattr(npc, "metadata", None)
    if not isinstance(meta, dict):
        meta = {}
        npc.metadata = meta
    meta.setdefault("hunger", 20)
    meta.setdefault("fatigue", 10)
    return meta


def get_hunger(npc) -> int:
    return _ensure(npc).get("hunger", 0)


def get_fatigue(npc) -> int:
    return _ensure(npc).get("fatigue", 0)


def tick_needs(npc, elapsed_minutes: int) -> None:
    """Apply need decay over elapsed game time."""
    meta = _ensure(npc)
    hours = elapsed_minutes / 60.0
    meta["hunger"] = min(100, meta["hunger"] + HUNGER_PER_HOUR * hours)
    # Fatigue only grows while not sleeping
    if meta.get("activity") != "sleep":
        meta["fatigue"] = min(100, meta["fatigue"] + FATIGUE_PER_HOUR * hours)


def feed(npc, amount: int = 40) -> None:
    """Reduce hunger; called when NPC eats."""
    meta = _ensure(npc)
    meta["hunger"] = max(0, meta["hunger"] - amount)


def rest(npc, amount: int = 50) -> None:
    """Reduce fatigue; called when NPC sleeps/rests."""
    meta = _ensure(npc)
    meta["fatigue"] = max(0, meta["fatigue"] - amount)


def need_descriptor(npc) -> str:
    h, f = get_hunger(npc), get_fatigue(npc)
    parts = []
    if h >= HUNGER_STARVING:
        parts.append("starving")
    elif h >= HUNGER_HUNGRY:
        parts.append("hungry")
    if f >= FATIGUE_EXHAUSTED:
        parts.append("exhausted")
    elif f >= FATIGUE_TIRED:
        parts.append("tired")
    return ", ".join(parts) if parts else "comfortable"
