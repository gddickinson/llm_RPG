"""The undead (George: expand the undead world). The dead that walk —
skeletons, zombies, ghouls, wights, wraiths, ghosts, mummies, vampires,
revenants, liches — share a common nature: no living heart to poison, no
mind to frighten, a recoil from holy light and cleansing fire. This is
the pure trait layer over `data/undead.json` (immunities, resistances,
weaknesses) + the two powers over the dead: a cleric's TURN UNDEAD (the
destroy/rout power) and the necromancer's raise/command (in
`engine/necromancy`).

`is_undead` reads the flag `world/monsters` stamps from a template's
`undead: true`, OR a living thing MADE undead (a lich ritual, a vampire's
bite) via `metadata["undead"]`. Consumed by `combat_math` (damage types),
`status_effects` (immunities), and the turn/raise powers.
"""

import json
import logging
import os

logger = logging.getLogger("llm_rpg.undead")

_DATA = os.path.join(os.path.dirname(__file__), "..", "data", "undead.json")
_T = None


def _traits():
    global _T
    if _T is None:
        try:
            with open(_DATA, encoding="utf-8") as fh:
                _T = json.load(fh)
        except Exception as e:                       # pragma: no cover
            logger.info(f"Undead data unavailable: {e}")
            _T = {"universal": {}, "by_type": {}}
    return _T


def is_undead(character) -> bool:
    return bool((getattr(character, "metadata", None) or {}).get("undead"))


def undead_type(character) -> str:
    return (getattr(character, "metadata", None) or {}).get("undead_type", "")


def _merged(character) -> dict:
    """Universal traits with the creature's own type layered on top."""
    uni = _traits().get("universal", {})
    typ = _traits().get("by_type", {}).get(undead_type(character), {})
    weak = dict(uni.get("weak", {}))
    weak.update(typ.get("weak", {}))
    resist = dict(uni.get("resist", {}))
    resist.update(typ.get("resist", {}))
    return {
        "immune_status": set(uni.get("immune_status", [])),
        "immune_damage": set(uni.get("immune_damage", [])),
        "weak": weak, "resist": resist,
    }


def damage_multiplier(defender, damage_kind: str) -> float:
    """How a damage KIND fares against this undead (1.0 vs the living)."""
    if not is_undead(defender):
        return 1.0
    kind = (damage_kind or "").lower()
    t = _merged(defender)
    if kind in t["immune_damage"]:
        return 0.0
    if kind in t["weak"]:
        return float(t["weak"][kind])
    if kind in t["resist"]:
        return float(t["resist"][kind])
    return 1.0


def immune_to_status(character, status: str) -> bool:
    if not is_undead(character):
        return False
    return status in _merged(character)["immune_status"]


# ---- TURN UNDEAD — the destroy / rout power (clerics, paladins) --------

TURN_RADIUS = 5


def can_turn(character) -> bool:
    cls = getattr(getattr(character, "character_class", None), "value", "")
    return cls in ("cleric", "paladin", "monk", "druid")


def turn_undead(engine, caster) -> str:
    """A channel of holy power: nearby undead are seared with radiance and
    routed; the frailer ones crumble outright. Scales with the channeler's
    level + Wisdom."""
    cx, cy = caster.position
    wis = getattr(caster, "wisdom", 10)
    power = getattr(caster, "level", 1) + max(0, (wis - 10) // 2)
    dmg = 4 + power                        # radiant damage
    hit, slain = [], []
    for npc in list(engine.npc_manager.npcs.values()):
        if not npc.is_active() or not is_undead(npc):
            continue
        nx, ny = npc.position
        if max(abs(nx - cx), abs(ny - cy)) > TURN_RADIUS:
            continue
        real = int(dmg * damage_multiplier(npc, "radiant"))
        npc.take_damage(real)
        if not npc.is_alive():
            slain.append(npc.name)
            try:                               # loot/XP/cleanup via the real path
                engine.combat_system._handle_defeat(caster, npc, real)
            except Exception as e:
                logger.debug(f"turn_undead defeat handling: {e}")
        else:
            hit.append(npc)
            meta = npc.metadata
            meta["broken"] = True             # rout — flees the holy light
            meta["fleeing"] = True
            meta["morale"] = 0
    if not hit and not slain:
        return "You channel holy power, but no undead stand within its light."
    parts = []
    if slain:
        parts.append(f"crumble to dust: {', '.join(slain)}")
    if hit:
        parts.append(f"{len(hit)} are seared and flee the light")
    msg = "You raise holy power against the dead — " + "; ".join(parts) + "."
    try:
        engine.memory_manager.add_event("[Turn] " + msg)
    except Exception:
        pass
    return msg
