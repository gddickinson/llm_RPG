"""Status effects — temporary buffs/debuffs that tick down each turn.

Each effect is recorded as a dict on the character's metadata under
`status_effects`. Each entry has a `name`, remaining `duration`, and
optional `data` (e.g. damage per tick).

Effects supported:
- poisoned: 1 damage per turn
- paralyzed: cannot act
- blessed: +1 to attack damage
- water_walking: cross water like solid ground (P11.3)
- frightened N: -N to every check and attack, decays 1/turn (P12.2)
- persistent_damage: damage each turn until a flat DC 15 check ends it
- prone: -2 attack, -2 AC; standing costs the next action
- blinded: visibility 1 for the player, -4 attack
- off_guard: -2 AC (applied by flanking; replaces the old +2 to-hit)
- well_rested: +10% XP (a private inn room, P12.6)
- swimmers_grace: +5 to swim and struggle checks (P11.3)
- flying: movement ignores ground-tile rules (P11.4)
- hasted: every second step is free; slowed: steps cost double (P11.4)
- cursed: -1 to attack damage
- frightened: random chance to skip turn

Apply via `apply_effect(char, name, duration)`. Tick all of a character's
effects each turn via `tick_effects(char, engine)`.
"""

import logging
import random
from typing import Any, Dict, List

logger = logging.getLogger("llm_rpg.status_effects")


VALID_EFFECTS = ("poisoned", "paralyzed", "blessed",
                 "cursed", "frightened", "stunned",
                 "water_walking", "swimmers_grace",
                 "flying", "hasted", "slowed",
                 "prone", "blinded", "off_guard",
                 "persistent_damage", "well_rested",
                 "keen_sight")     # P14.2: magical sight through walls

# Valued conditions (P12.2, PF2e): entries may carry a "value";
# these decay by 1 at end of turn and expire at 0 (duration ignored)
DECAYING_VALUES = ("frightened",)
PERSIST_END_DC = 15         # flat check to stop persistent damage


def _slot(character) -> List[Dict[str, Any]]:
    meta = getattr(character, "metadata", None)
    if not isinstance(meta, dict):
        meta = {}
        character.metadata = meta
    meta.setdefault("status_effects", [])
    return meta["status_effects"]


def apply_effect(character, name: str, duration: int,
                 data: Dict[str, Any] = None, value: int = 0) -> None:
    """Add (or refresh) a status effect; `value` makes it a PF2e
    valued condition (Frightened 2 = -2 to everything)."""
    if name not in VALID_EFFECTS:
        logger.warning(f"Unknown status effect: {name}")
        return
    try:   # the dead feel no poison, plague or fear (undead immunities)
        from engine.undead import immune_to_status
        if immune_to_status(character, name):
            return
    except Exception:
        pass
    effects = _slot(character)
    # Refresh existing
    for e in effects:
        if e["name"] == name:
            e["duration"] = max(e["duration"], duration)
            e["value"] = max(e.get("value", 0), value)
            if data:
                e.setdefault("data", {}).update(data)
            return
    effects.append({"name": name, "duration": duration,
                    "value": value, "data": data or {}})


def effect_value(character, name: str) -> int:
    for e in _slot(character):
        if e["name"] == name:
            return e.get("value", 0)
    return 0


def has_effect(character, name: str) -> bool:
    return any(e["name"] == name for e in _slot(character))


def remove_effect(character, name: str) -> None:
    effects = _slot(character)
    character.metadata["status_effects"] = [
        e for e in effects if e["name"] != name]


def list_effects(character) -> List[Dict[str, Any]]:
    return list(_slot(character))


def tick_effects(character, engine=None,
                 rng: random.Random = None) -> List[str]:
    """Apply per-turn effect logic, decrement durations, expire.

    Returns a list of event strings for the event log.
    """
    rng = rng or random
    events = []
    effects = _slot(character)
    survivors = []
    for e in effects:
        name = e["name"]
        if name == "poisoned":
            character.take_damage(1)
            events.append(f"{character.name} suffers from poison (-1 HP).")
            if not character.is_alive():
                events.append(f"{character.name} succumbs to poison!")
        elif name == "persistent_damage":
            amount = e.get("data", {}).get("amount", 1)
            kind = e.get("data", {}).get("kind", "bleeding")
            character.take_damage(amount)
            events.append(
                f"{character.name} suffers {kind} (-{amount} HP).")
            if not character.is_alive():
                events.append(f"{character.name} succumbs!")
            if rng.randint(1, 20) >= PERSIST_END_DC:   # flat check
                events.append(
                    f"{character.name}'s {kind} stops.")
                continue
            survivors.append(e)
            continue
        # paralyzed / blessed / cursed / prone / blinded / off_guard
        # are passive: other systems query has_effect()/penalties

        if name in DECAYING_VALUES and e.get("value", 0) > 0:
            e["value"] -= 1                    # PF2e decay (P12.2)
            if e["value"] <= 0:
                events.append(
                    f"{character.name}'s {name} fades.")
            else:
                survivors.append(e)
            continue

        e["duration"] -= 1
        if e["duration"] > 0:
            survivors.append(e)
        else:
            events.append(
                f"{character.name}'s {name} effect fades.")
    character.metadata["status_effects"] = survivors
    return events


def check_penalty(character) -> int:
    """Penalty applied to EVERY d20 check (P12.2)."""
    return -effect_value(character, "frightened")


def attack_penalty(character) -> int:
    """Penalty to attack rolls from conditions (P12.2)."""
    pen = -effect_value(character, "frightened")
    if has_effect(character, "blinded"):
        pen -= 4
    if has_effect(character, "prone"):
        pen -= 2
    return pen


def ac_penalty(character) -> int:
    """AC reduction from conditions (negative or 0)."""
    pen = 0
    if has_effect(character, "off_guard"):
        pen -= 2
    if has_effect(character, "prone"):
        pen -= 2
    return pen


def can_act(character) -> bool:
    """Whether the character can take a turn this round."""
    return not (has_effect(character, "paralyzed") or
                has_effect(character, "stunned"))


def attack_damage_modifier(character) -> int:
    """Bonus/penalty from blessed/cursed status."""
    mod = 0
    if has_effect(character, "blessed"):
        mod += 1
    if has_effect(character, "cursed"):
        mod -= 1
    return mod
