"""P27.2 — passive wound recovery.

Chronic low HP was the default state: the hero only mended at a bed or from a
potion, so every fight left it a sliver until it found an inn. Now a wound
knits slowly ON ITS OWN when you're safe and provided for — accessible
recovery that never trivialises a hard fight: no threat may be near, and a
DYING, STARVING, PARCHED, or badly INFECTED body doesn't heal. Faster while
well-rested. Pairs with M.8a (the away-agent's rest) and the potion/Heal path.
"""

from characters.needs import (get_hunger, get_thirst,
                               HUNGER_STARVING, THIRST_PARCHED)

REGEN_INTERVAL = 8         # +1 HP per N safe game-minutes
RESTED_INTERVAL = 5        # faster while well-rested
THREAT_RADIUS = 3          # a hostile this near keeps the wound raw
INFECTION_BLOCK = 60       # a fouling wound won't knit
_HOSTILE = ("brigand", "monster", "troll")


def _threat_near(engine, pos, r: int = THREAT_RADIUS) -> bool:
    """A hostile within `r` tiles — you don't heal with a foe closing in."""
    for npc in engine.npc_manager.npcs.values():
        if not npc.is_active():
            continue
        if getattr(getattr(npc, "character_class", None), "value", "") \
                not in _HOSTILE:
            continue
        px, py = getattr(npc, "position", (None, None))
        if px is None:
            continue
        if max(abs(px - pos[0]), abs(py - pos[1])) <= r:
            return True
    return False


def can_regen(engine) -> bool:
    """Is the player in a state where a wound naturally heals right now?"""
    p = getattr(engine, "player", None)
    if p is None or p.hp <= 0 or p.hp >= p.max_hp:
        return False
    meta = getattr(p, "metadata", {}) or {}
    if meta.get("dying"):
        return False
    if get_hunger(p) >= HUNGER_STARVING or get_thirst(p) >= THIRST_PARCHED:
        return False
    if meta.get("infection", 0) >= INFECTION_BLOCK:
        return False
    if _threat_near(engine, p.position):
        return False
    return True


def regen_interval(engine) -> int:
    """How many safe minutes between HP ticks — shorter while well-rested."""
    try:
        from characters.status_effects import has_effect
        if has_effect(engine.player, "well_rested"):
            return RESTED_INTERVAL
    except Exception:
        pass
    return REGEN_INTERVAL


def tick_hp_regen(engine) -> int:
    """Once every `regen_interval` safe minutes, knit a point of HP. Returns
    the HP restored this tick (0 on most turns)."""
    if not can_regen(engine):
        return 0
    if engine.turn_counter % regen_interval(engine) != 0:
        return 0
    p = engine.player
    heal = min(p.max_hp - p.hp, 1)
    p.hp += heal
    return heal
