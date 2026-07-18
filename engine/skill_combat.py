"""T4.4 — skills feed combat power (pure, data-driven).

The 12-skill lattice gated only gathering/traversal — there was no path from
"L40 smith" to "stronger in a fight". Now a few skills also sharpen you in
combat, read from each skill's optional `combat` block in `data/skills.json`:

- **smithing** hones your gear — a smith keeps a keen edge and sound armour
  (`weapon_damage_per` → +weapon damage, `armor_ac_per` → +AC).
- **agility** makes you harder to hit (`dodge_ac_per` → +AC).
- **hunting** makes you deadlier to beasts (`beast_damage_per` → +damage vs a
  monster/animal quarry).

Each tie is `+1 per N skill levels`, so it rewards investment without eclipsing
gear (skills cap at 50 → a modest handful of points). Every field is optional;
a skill with no `combat` block contributes nothing. Consumed by `engine/effects`
(AC + weapon damage) and `engine/combat_system` (the beast bonus).
"""

from engine.skill_progression import _load_skills, get_skill_level

_BEAST_CLASSES = ("monster", "animal", "beast")


def _combat_cfg(skill_id: str) -> dict:
    return (_load_skills().get(skill_id, {}) or {}).get("combat", {}) or {}


def _step_bonus(character, skill_id: str, key: str) -> int:
    """+1 per `per` levels of `skill_id` (0 when the skill has no such tie)."""
    per = _combat_cfg(skill_id).get(key, 0)
    try:
        per = int(per)
    except (TypeError, ValueError):
        per = 0
    if per <= 0:
        return 0
    return get_skill_level(character, skill_id) // per


def weapon_damage_bonus(character) -> int:
    """Extra melee/ranged damage from a well-kept blade (smithing)."""
    return _step_bonus(character, "smithing", "weapon_damage_per")


def armor_ac_bonus(character) -> int:
    """Extra AC from sound armour (smithing) + nimble footwork (agility)."""
    return (_step_bonus(character, "smithing", "armor_ac_per")
            + _step_bonus(character, "agility", "dodge_ac_per"))


def beast_damage_bonus(character, target) -> int:
    """A hunter strikes a beast (monster/animal) harder; 0 vs people."""
    klass = getattr(getattr(target, "character_class", None), "value", "")
    if klass not in _BEAST_CLASSES:
        return 0
    return _step_bonus(character, "hunting", "beast_damage_per")


def combat_summary(character):
    """UI: one line per non-zero combat tie the character currently has, so the
    player SEES that a skill sharpens their fighting (T2 'make it felt')."""
    lines = []
    wd = weapon_damage_bonus(character)
    if wd:
        lines.append(f"Smithing: +{wd} weapon damage")
    sm_ac = _step_bonus(character, "smithing", "armor_ac_per")
    if sm_ac:
        lines.append(f"Smithing: +{sm_ac} AC (sound armour)")
    ag_ac = _step_bonus(character, "agility", "dodge_ac_per")
    if ag_ac:
        lines.append(f"Agility: +{ag_ac} AC (dodge)")
    hb = _step_bonus(character, "hunting", "beast_damage_per")
    if hb:
        lines.append(f"Hunting: +{hb} damage vs beasts")
    return lines
