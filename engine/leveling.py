"""Leveling system — XP thresholds, level-up effects.

XP curve (cumulative XP needed to reach level N) — a slow, deliberate climb where
power leans on gear + companions as much as raw levels:
    level 1: 0        (starting level)
    level 2: 300
    level 3: 900
    level 5: 3000
    level 8: 8400
    level N: XP_CURVE_COEFF * N * (N - 1)   (XP_CURVE_COEFF = 150)

BALANCE FIX (T0.1, 2026-07-18): P37.6 took the curve 10x steeper (COEFF 150→1500)
"for much more XP per level", but that OVERSHOT catastrophically — the entire
35-quest authored questbook awards ~10,000 XP total, which at COEFF=1500 reaches
only LEVEL 2, leaving the L12/L16 campaign-finale dragon mathematically unreachable
without thousands of grind kills. Reverting to COEFF=150 restores the intended
pace (~8 same-level kills for the first level; a tougher foe pays far more —
25 + 15*foe_level) AND lands a hero who finishes the questline near ~L8, so the
finale is a reachable, aspirational fight rather than a wall. Power still leans on
gear + party, not XP.

Per level-up the character gains:
    +5 max_hp (and full heal)
    +1 to two ability scores chosen by class
"""

import logging
from typing import Dict, List, Tuple

from characters.character_types import CharacterClass

logger = logging.getLogger("llm_rpg.leveling")

MAX_LEVEL = 20
XP_CURVE_COEFF = 150     # xp_threshold(L) = COEFF*L*(L-1); T0.1 revert of the P37.6
#                          1500 overshoot that made the campaign finale unreachable

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

        # T1.2: a level-up also grants a PERK POINT to spend on a build choice —
        # so a level is a decision, not just +5 HP (the review's build-agency fix)
        try:
            from engine.perks import award_perk_point
            award_perk_point(character)
        except Exception:
            pass

        msg = (
            f"** Level up! {character.name} reaches level {character.level} "
            f"(+5 HP, +1 {favors[0].upper()[:3]}, +1 {favors[1].upper()[:3]}, "
            f"+1 perk point) **"
        )
        msgs.append(msg)
        logger.info(msg)

        # Sanity: ability scores soft-cap
        for stat in ("strength", "dexterity", "constitution",
                     "intelligence", "wisdom", "charisma"):
            v = getattr(character, stat, 10)
            if v > 30:
                setattr(character, stat, 30)

    # M1: a caster who has climbed a tier learns the class spells they now
    # qualify for (the innate/trained route; wizards ALSO study from tomes)
    if msgs:
        try:
            from engine.spells import learn_new_spells
            learnt = learn_new_spells(character)
            if learnt:
                msgs.append(f"** New magic mastered: {', '.join(learnt)}. **")
        except Exception:
            pass

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
