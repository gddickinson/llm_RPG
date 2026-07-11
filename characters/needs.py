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
THIRST_PER_HOUR = 4      # thirst is a faster clock than hunger

HUNGER_HUNGRY = 60
HUNGER_STARVING = 90
FATIGUE_TIRED = 60
FATIGUE_EXHAUSTED = 90
THIRST_THIRSTY = 60
THIRST_PARCHED = 90
SLEEP_DEBT_MAX = 3       # days of missed real sleep that count


def _ensure(npc) -> dict:
    meta = getattr(npc, "metadata", None)
    if not isinstance(meta, dict):
        meta = {}
        npc.metadata = meta
    meta.setdefault("hunger", 20)
    meta.setdefault("fatigue", 10)
    meta.setdefault("thirst", 15)
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


def tick_player_needs(player, elapsed_minutes: int) -> None:
    """Player: hunger, thirst, and waking tiredness all grow
    (P12.3 — the player finally NEEDS to sleep and drink)."""
    meta = _ensure(player)
    hours = elapsed_minutes / 60.0
    meta["hunger"] = min(100, meta["hunger"] + HUNGER_PER_HOUR * hours)
    meta["thirst"] = min(100, meta["thirst"] + THIRST_PER_HOUR * hours)
    meta["fatigue"] = min(100,
                          meta["fatigue"] + FATIGUE_PER_HOUR * hours)


def get_thirst(char) -> int:
    return int(_ensure(char).get("thirst", 0))


def drink(char, amount: int = 100) -> None:
    meta = _ensure(char)
    meta["thirst"] = max(0, meta["thirst"] - amount)


# ---- the exhaustion ladder (P12.3, 5e-style, cumulative) -----------

def exhaustion_level(char) -> int:
    """0-6. Tiredness, starvation, thirst and SLEEP DEBT stack.
    CDDA's two tracks: fatigue clears with any sleep; sleep_debt
    only with real nights in a bed."""
    meta = _ensure(char)
    lvl = 0
    if meta.get("fatigue", 0) >= FATIGUE_EXHAUSTED:
        lvl += 1
    if meta.get("hunger", 0) >= HUNGER_STARVING:
        lvl += 1
    thirst = meta.get("thirst", 0)
    if thirst >= THIRST_PARCHED:
        lvl += 2
    elif thirst >= THIRST_THIRSTY:
        lvl += 1
    lvl += min(2, int(meta.get("sleep_debt", 0)))
    return min(6, lvl)


def exhaustion_check_penalty(char) -> int:
    """Level N = -N to every d20 (ladder rung 1: checks suffer)."""
    return -exhaustion_level(char)


def exhaustion_attack_penalty(char) -> int:
    """Rung 3: attacks suffer too."""
    return -2 if exhaustion_level(char) >= 3 else 0


def exhaustion_step_minutes(char) -> int:
    """Rung 2: speed halves; rung 5: you can barely walk."""
    lvl = exhaustion_level(char)
    if lvl >= 5:
        return 3
    if lvl >= 2:
        return 1
    return 0


def player_needs_turn(engine) -> None:
    """One per-turn pass: growth, warnings, drains, the collapse.
    Called from advance_turn; replaces the old inline hunger block."""
    player = engine.player
    meta = _ensure(player)
    before_h = meta.get("hunger", 0)
    before_t = meta.get("thirst", 0)
    tick_player_needs(player, elapsed_minutes=1)
    hunger, thirst = meta["hunger"], meta["thirst"]
    # warnings on threshold crossings; drains on the deep end
    if hunger >= HUNGER_STARVING and engine.world.time % 30 == 0:
        if player.hp > 1:
            player.hp -= 1
        engine.memory_manager.add_event(
            "You are starving! Find something to eat.")
    elif before_h < HUNGER_HUNGRY <= hunger:
        engine.memory_manager.add_event(
            "Your stomach growls. You should eat soon.")
    if thirst >= THIRST_PARCHED and engine.world.time % 20 == 0:
        if player.hp > 1:
            player.hp -= 1
        engine.memory_manager.add_event(
            "[!] You are parched — find water!")
    elif before_t < THIRST_THIRSTY <= thirst:
        engine.memory_manager.add_event(
            "Your throat is dry. You should drink soon.")
    # ladder rung 4: HP max halves while this deep
    lvl = exhaustion_level(player)
    if lvl >= 4 and player.hp > player.max_hp // 2:
        player.hp = player.max_hp // 2
    try:   # torso wounds cap effective HP (P15.9)
        from engine.wounds import apply_hp_ceiling
        apply_hp_ceiling(player)
    except Exception:
        pass
    # rung 6: collapse — any sleep clears tiredness, not the debt
    if lvl >= 6:
        from characters.status_effects import apply_effect, has_effect
        if not has_effect(player, "paralyzed"):
            apply_effect(player, "paralyzed", duration=8)
            meta["fatigue"] = 50
            engine.memory_manager.add_event(
                "[!] You collapse from exhaustion where you stand!")


def run_player_night(engine, ended_day: int) -> None:
    """Day boundary: a night NOT slept in a bed is sleep debt."""
    meta = _ensure(engine.player)
    if meta.get("slept_day") == ended_day:
        return
    meta["sleep_debt"] = min(SLEEP_DEBT_MAX,
                             int(meta.get("sleep_debt", 0)) + 1)
    if meta["sleep_debt"] >= 2:
        engine.memory_manager.add_event(
            "[!] Another night without real sleep — you are wearing "
            "thin.")


def hunger_attack_penalty(char) -> int:
    """Damage penalty while hungry (-1) or starving (-2)."""
    h = get_hunger(char)
    if h >= HUNGER_STARVING:
        return -2
    if h >= HUNGER_HUNGRY:
        return -1
    return 0


def need_descriptor(npc) -> str:
    h, f = get_hunger(npc), get_fatigue(npc)
    parts = []
    if h >= HUNGER_STARVING:
        parts.append("starving")
    elif h >= HUNGER_HUNGRY:
        parts.append("hungry")
    t = get_thirst(npc)
    if t >= THIRST_PARCHED:
        parts.append("parched")
    elif t >= THIRST_THIRSTY:
        parts.append("thirsty")
    if f >= FATIGUE_EXHAUSTED:
        parts.append("exhausted")
    elif f >= FATIGUE_TIRED:
        parts.append("tired")
    return ", ".join(parts) if parts else "comfortable"
