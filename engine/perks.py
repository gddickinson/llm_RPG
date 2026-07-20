"""T1.2 level-up PERKS — build agency.

The review found level-ups are a deterministic +5 HP + 2 fixed stats, so two
warriors are identical and there's no "I want to reach the next level to unlock X".
Each level-up now grants a PERK POINT the player spends on a choice from
`data/perks.json`. A perk's numeric `bonuses` fold into `engine.effects`'
aggregation (so they feed AC / damage / stats / HP just like equipment); state
lives on `player.metadata` (rides the save).

Pure/heuristic — no UI here; `grant_perk`/`award_perk_point` are the engine API the
level-up flow and the perk overlay call.
"""

import json
import os
from functools import lru_cache
from typing import Dict, List

_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "perks.json")


@lru_cache(maxsize=1)
def all_perks() -> Dict[str, dict]:
    try:
        with open(_PATH) as fh:
            return json.load(fh)
    except Exception:
        return {}


def _meta(character) -> dict:
    m = getattr(character, "metadata", None)
    if not isinstance(m, dict):
        m = {}
        try:
            character.metadata = m
        except Exception:
            pass
    return m


def owned(character) -> List[str]:
    return list(_meta(character).get("perks", []))


def has_perk(character, pid: str) -> bool:
    return pid in owned(character)


def perk_points(character) -> int:
    return int(_meta(character).get("perk_points", 0))


def _class_ok(character, spec: dict) -> bool:
    req = spec.get("requires_class")
    if not req:
        return True
    cls = getattr(getattr(character, "character_class", None), "value", "")
    return cls in req


def available_perks(character) -> List[str]:
    """Perk ids the character qualifies for and hasn't taken yet."""
    have = set(owned(character))
    return [pid for pid, spec in all_perks().items()
            if pid not in have and _class_ok(character, spec)]


def perk_bonuses(character) -> Dict[str, int]:
    """Summed numeric bonuses from every owned perk (folded into effects)."""
    out: Dict[str, int] = {}
    perks = all_perks()
    for pid in owned(character):
        for key, val in (perks.get(pid, {}).get("bonuses", {}) or {}).items():
            try:
                out[key] = out.get(key, 0) + int(val)
            except Exception:
                pass
    return out


def award_perk_point(character, n: int = 1) -> None:
    m = _meta(character)
    m["perk_points"] = int(m.get("perk_points", 0)) + n


def grant_perk(character, pid: str) -> bool:
    """Learn `pid` (spends a perk point if one is available). Returns success.
    A max_hp perk bumps the live pool immediately so the level-up heals into it."""
    spec = all_perks().get(pid)
    if spec is None or has_perk(character, pid) or not _class_ok(character, spec):
        return False
    m = _meta(character)
    m.setdefault("perks", []).append(pid)
    if int(m.get("perk_points", 0)) > 0:
        m["perk_points"] = int(m["perk_points"]) - 1
    hp = int((spec.get("bonuses") or {}).get("max_hp", 0))
    if hp:
        try:
            character.max_hp = int(getattr(character, "max_hp", 0)) + hp
            character.hp = min(getattr(character, "hp", 0) + hp, character.max_hp)
        except Exception:
            pass
    return True
