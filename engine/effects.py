"""Equipment bonus aggregator.

Equipped items can carry an `equip_bonuses` dict that contributes to the
wearer's effective stats. The base Character attributes never change;
combat / UI code instead queries the `effective_*` helpers here.

Recognized bonus keys:
    strength, dexterity, constitution, intelligence, wisdom, charisma
    max_hp, max_mana
    armor (extra AC)
    damage (extra weapon damage when this is the held weapon)
    hp_regen, mana_regen
    dodge (extra AC; treated identical to armor for hit resolution)

Status effects (blessed / cursed) are layered on top via
`characters.status_effects.attack_damage_modifier`.
"""

import logging
from typing import Dict, Iterable

logger = logging.getLogger("llm_rpg.effects")


_ABILITY_KEYS = ("strength", "dexterity", "constitution",
                 "intelligence", "wisdom", "charisma")


def _gather_bonuses(character) -> Dict[str, int]:
    """Sum equip_bonuses across all equipped items."""
    try:
        from characters.equipment import equipped_items
    except Exception:
        return {}
    out: Dict[str, int] = {}
    from engine.durability import is_broken
    for it in equipped_items(character):
        if is_broken(it):
            continue
        bonus = getattr(it, "equip_bonuses", None) or {}
        for key, val in bonus.items():
            out[key] = out.get(key, 0) + int(val)
    try:                                 # T1.2 perk bonuses fold into the same
        from engine.perks import perk_bonuses   # aggregation → AC/damage/stats/HP
        for key, val in perk_bonuses(character).items():
            out[key] = out.get(key, 0) + int(val)
    except Exception:
        pass
    return out


def effective_stat(character, stat_name: str) -> int:
    """Base + equipment for a single ability score."""
    base = int(getattr(character, stat_name, 10))
    bonuses = _gather_bonuses(character)
    return base + int(bonuses.get(stat_name, 0))


def ability_modifier(value: int) -> int:
    return (value - 10) // 2


def effective_ability_mod(character, stat_name: str) -> int:
    return ability_modifier(effective_stat(character, stat_name))


def proficiency_bonus(character) -> int:
    """Standard D&D 5e proficiency by level."""
    level = max(1, int(getattr(character, "level", 1)))
    return 2 + (level - 1) // 4


def effective_max_hp(character) -> int:
    base = int(getattr(character, "max_hp", 10))
    return base + int(_gather_bonuses(character).get("max_hp", 0))


def effective_max_mana(character) -> int:
    meta = getattr(character, "metadata", None) or {}
    base = int(meta.get("max_mana", 0))
    return base + int(_gather_bonuses(character).get("max_mana", 0))


def total_armor_value(character) -> int:
    """Sum of armor + shield AC contributions from equipped slots."""
    try:
        from characters.equipment import get_equipment
    except Exception:
        return 0
    from engine.durability import is_broken
    eq = get_equipment(character)
    total = 0
    for slot in ("armor", "shield"):
        item = eq.get(slot)
        if item and not is_broken(item):
            total += int(getattr(item, "armor", 0))
    try:   # a matched set is worth more than its pieces (P15.10)
        from characters.equipment import set_bonus
        total += set_bonus(character)[0]
    except Exception:
        pass
    return total


def effective_ac(character) -> int:
    """D&D-style AC: 10 + DEX_mod + armor + shield + ring/etc bonuses."""
    dex_mod = effective_ability_mod(character, "dexterity")
    armor = total_armor_value(character)
    bonus_armor = _gather_bonuses(character).get("armor", 0)
    bonus_dodge = _gather_bonuses(character).get("dodge", 0)
    skill_ac = _skill_combat_ac(character)          # T4.4 smithing + agility
    return 10 + dex_mod + armor + bonus_armor + bonus_dodge + skill_ac


def effective_weapon_damage_bonus(character) -> int:
    """Extra damage from item enchantments (e.g. flaming sword +3) plus a
    smith's well-kept edge (T4.4 smithing)."""
    from engine import skill_combat
    return (_gather_bonuses(character).get("damage", 0)
            + skill_combat.weapon_damage_bonus(character))


def _skill_combat_ac(character) -> int:
    from engine import skill_combat
    return skill_combat.armor_ac_bonus(character)


def list_equipment_bonuses(character) -> Dict[str, int]:
    """Convenience for the UI: full bonus dict."""
    return _gather_bonuses(character)


def regen_tick(character) -> None:
    """Apply HP / mana regen from equipment. Call once per turn."""
    bonuses = _gather_bonuses(character)
    hp_regen = int(bonuses.get("hp_regen", 0))
    mana_regen = int(bonuses.get("mana_regen", 0))
    if hp_regen > 0 and character.hp < effective_max_hp(character):
        character.hp = min(effective_max_hp(character),
                           character.hp + hp_regen)
    if mana_regen > 0:
        meta = getattr(character, "metadata", None)
        if isinstance(meta, dict):
            cur = meta.get("mana", 0)
            cap = effective_max_mana(character)
            meta["mana"] = min(cap, cur + mana_regen)
