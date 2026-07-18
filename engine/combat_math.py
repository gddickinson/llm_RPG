"""Pure combat math split out of combat_system.py (kept < 500 lines).

Damage-type matchups — the little rock-paper-scissors that makes the
right weapon matter: silver bites trolls and monsters, holy sears the
wicked, fire denies a troll its regeneration — plus a hunter's skilled
edge against beasts (T4.4).
"""


def damage_type_modifier(attacker, defender, damage: int) -> int:
    """Silver vs trolls/undead, holy vs the wicked, fire vs trolls, then a
    hunter's flat bonus vs a beast (T4.4 skills feed combat power)."""
    damage = _type_multiplier(attacker, defender, damage)
    try:
        from engine.skill_combat import beast_damage_bonus
        damage += beast_damage_bonus(attacker, defender)
    except Exception:
        pass
    return damage


def _type_multiplier(attacker, defender, damage: int) -> int:
    try:
        from characters.equipment import equipped_weapon
        w = equipped_weapon(attacker)
        if w is None:
            return damage
        kind = (w.damage_kind or "slash").lower()
        target_class = getattr(defender.character_class, "value", "")
        target_race = getattr(defender.race, "value", "")

        # Silver / holy vs troll, monster
        if "silver" in (w.id or "") or "silver" in (w.name.lower() or ""):
            if target_race == "troll" or target_class in ("troll", "monster"):
                return int(damage * 1.5)
        if kind == "holy" and target_class in ("monster", "brigand"):
            return int(damage * 1.3)
        # Fire vs troll (regenerator)
        if kind == "fire" and target_race == "troll":
            return int(damage * 1.5)
    except Exception:
        pass
    return damage
