"""Status effects — temporary buffs/debuffs that tick down each turn.

Each effect is recorded as a dict on the character's metadata under
`status_effects`. Each entry has a `name`, remaining `duration`, and
optional `data` (e.g. damage per tick).

Effects supported:
- poisoned: 1 damage per turn
- paralyzed: cannot act
- blessed: +1 to attack damage
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
                 "cursed", "frightened", "stunned")


def _slot(character) -> List[Dict[str, Any]]:
    meta = getattr(character, "metadata", None)
    if not isinstance(meta, dict):
        meta = {}
        character.metadata = meta
    meta.setdefault("status_effects", [])
    return meta["status_effects"]


def apply_effect(character, name: str, duration: int,
                 data: Dict[str, Any] = None) -> None:
    """Add (or refresh) a status effect."""
    if name not in VALID_EFFECTS:
        logger.warning(f"Unknown status effect: {name}")
        return
    effects = _slot(character)
    # Refresh existing
    for e in effects:
        if e["name"] == name:
            e["duration"] = max(e["duration"], duration)
            if data:
                e.setdefault("data", {}).update(data)
            return
    effects.append({"name": name, "duration": duration,
                    "data": data or {}})


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
        # paralyzed / blessed / cursed / frightened are passive: handled
        # by other systems that query has_effect()

        e["duration"] -= 1
        if e["duration"] > 0:
            survivors.append(e)
        else:
            events.append(
                f"{character.name}'s {name} effect fades.")
    character.metadata["status_effects"] = survivors
    return events


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
