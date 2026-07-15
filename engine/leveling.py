"""Leveling system — XP thresholds, level-up effects.

XP curve (cumulative XP needed to reach level N) — P37.5 rebalanced STEEPER so
the hero climbs slowly and power comes more from gear + companions than from
raw levels (George: "advances through levels much too quickly"):
    level 1: 0        (starting level)
    level 2: 120
    level 3: 360
    level 4: 720
    level N: XP_CURVE_COEFF * N * (N - 1)   (XP_CURVE_COEFF = 60)

With the P37.5 kill award (10 + 5*foe_level) that is ~8 same-level kills for the
first level and MORE per level after — a deliberate, gear-driven ramp (was ~2).

Per level-up the character gains:
    +5 max_hp (and full heal)
    +1 to two ability scores chosen by class
"""

import logging
from typing import Dict, List, Tuple

from characters.character_types import CharacterClass

logger = logging.getLogger("llm_rpg.leveling")

MAX_LEVEL = 20
XP_CURVE_COEFF = 60      # xp_threshold(L) = COEFF * L * (L-1); P37.5 (was 50)

# Stats favored by each class (gain +1 each on level-up)
CLASS_STAT_FAVORS: Dict[CharacterClass, Tuple[str, str]] = {
    CharacterClass.WARRIOR:   ("strength", "constitution"),
    CharacterClass.WIZARD:    ("intelligence", "wisdom"),
    CharacterClass.ROGUE:     ("dexterity", "charisma"),
    CharacterClass.CLERIC:    ("wisdom", "charisma"),
    CharacterClass.BARD:      ("charisma", "dexterity"),
    CharacterClass.MERCHANT:  ("charisma", "intelligence"),
    CharacterClass.GUARD:     ("strength", "constitution"),
    CharacterClass.RANGER:    ("dexterity", "wisdom"),
    CharacterClass.DRUID:     ("wisdom", "constitution"),
    CharacterClass.PALADIN:   ("strength", "charisma"),
    CharacterClass.MONK:      ("dexterity", "wisdom"),
    CharacterClass.SORCERER:  ("charisma", "constitution"),
    CharacterClass.WARLOCK:   ("charisma", "intelligence"),
    CharacterClass.BARBARIAN: ("strength", "constitution"),
    CharacterClass.ARTIFICER: ("intelligence", "dexterity"),
    CharacterClass.NOBLE:     ("charisma", "intelligence"),
    CharacterClass.VILLAGER:  ("constitution", "wisdom"),
}


def xp_threshold(level: int) -> int:
    """Cumulative XP needed to be at `level`. xp_threshold(1) == 0."""
    if level <= 1:
        return 0
    if level > MAX_LEVEL:
        level = MAX_LEVEL
    return XP_CURVE_COEFF * level * (level - 1)


def level_for_xp(xp: int) -> int:
    """Highest level the character qualifies for given XP."""
    level = 1
    while level < MAX_LEVEL and xp >= xp_threshold(level + 1):
        level += 1
    return level


def xp_to_next(xp: int) -> Tuple[int, int]:
    """Return (current_level_xp, xp_needed_to_next_level)."""
    lvl = level_for_xp(xp)
    if lvl >= MAX_LEVEL:
        return (xp - xp_threshold(MAX_LEVEL), 0)
    base = xp_threshold(lvl)
    nxt = xp_threshold(lvl + 1)
    return (xp - base, nxt - base)


def check_level_up(character) -> List[str]:
    """Apply any pending level-ups based on the character's current XP.

    Returns a list of human-readable strings describing each level-up,
    or empty list if no level-up occurred.

    Safe no-op on minimal mock objects (no `level` or `character_class`).
    """
    if not character or not hasattr(character, "level") \
            or not hasattr(character, "character_class"):
        return []
    meta = getattr(character, "metadata", None) or {}
    if not isinstance(meta, dict):
        meta = {}
        character.metadata = meta
    xp = meta.get("xp", 0)

    target = level_for_xp(xp)
    msgs: List[str] = []
    while character.level < target:
        character.level += 1
        # +5 HP
        character.max_hp += 5
        character.hp = character.max_hp  # full heal on level-up

        # +1 to favored stats
        favors = CLASS_STAT_FAVORS.get(character.character_class,
                                       ("strength", "constitution"))
        for stat in favors:
            setattr(character, stat, getattr(character, stat, 10) + 1)

        msg = (
            f"** Level up! {character.name} reaches level {character.level} "
            f"(+5 HP, +1 {favors[0].upper()[:3]}, +1 {favors[1].upper()[:3]}) **"
        )
        msgs.append(msg)
        logger.info(msg)

        # Sanity: ability scores soft-cap
        for stat in ("strength", "dexterity", "constitution",
                     "intelligence", "wisdom", "charisma"):
            v = getattr(character, stat, 10)
            if v > 30:
                setattr(character, stat, 30)

    return msgs


def award_xp(character, amount: int) -> List[str]:
    """Grant XP and apply any level-ups. Returns level-up messages."""
    meta = getattr(character, "metadata", None) or {}
    if not isinstance(meta, dict):
        meta = {}
        character.metadata = meta
    try:   # a good bed pays for itself (P12.6)
        from characters.status_effects import has_effect
        if has_effect(character, "well_rested"):
            amount = int(amount * 1.10)
    except Exception:
        pass
    meta["xp"] = meta.get("xp", 0) + max(0, int(amount))
    return check_level_up(character)
