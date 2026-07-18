"""M0 — the Worldcraft mutation layer (the keystone of Magic & Worldcraft).

George wants BOTH magical and non-magical world change, under CONSISTENT rules.
So every tile change routes through ONE validated facade over `WorldMap.set_terrain`
(the existing chokepoint): a spell, a mason, the player's build tool, and the DM
all obey the same ruleset in `data/worldcraft/mutations.json` — "what terrain can
become what, by what means, at what cost, gated on whom".

A rule (keyed by id) is `{from, to, verb, labor?, magic?}`:
- `labor` = `{skill, tool?, resources?, effort, yields?}` — how a WORKER/player
  does it by hand (skill level, a held tool, consumed materials, and by-products).
- `magic` = `{tag}` — the spell school that can do it (fire/nature/earth/water/
  force). Mana is the spell system's job; worldcraft just applies + charges labor.
A `means` absent from a rule ⇒ that means can't perform that change.

Persistence is FREE: the terrain grid is snapshotted whole by `save_load`, so any
mutation here survives a save with no extra code.
"""

import json
import os
from typing import Optional, Tuple

from world.world_map import TerrainType

_DATA = os.path.join(os.path.dirname(__file__), "..", "data",
                     "worldcraft", "mutations.json")
_RULES = None


def rules() -> dict:
    """The mutation rules table (loaded once)."""
    global _RULES
    if _RULES is None:
        try:
            with open(_DATA) as f:
                _RULES = json.load(f)
        except Exception:
            _RULES = {}
    return _RULES


def _tname(t) -> str:
    return t.value if isinstance(t, TerrainType) else str(t)


def rule_for(from_t, to_t) -> Optional[Tuple[str, dict]]:
    """The (id, rule) turning `from_t` into `to_t`, or None."""
    f, t = _tname(from_t), _tname(to_t)
    for rid, rule in rules().items():
        if rule.get("from") == f and rule.get("to") == t:
            return rid, rule
    return None


def allowed_targets(from_t, means: str = None) -> list:
    """Terrain names `from_t` can become (optionally filtered to a means)."""
    f = _tname(from_t)
    out = []
    for rule in rules().values():
        if rule.get("from") != f:
            continue
        if means and rule.get(means) is None:
            continue
        out.append(rule["to"])
    return out


# ---- gating helpers -------------------------------------------------------

def _count(actor, item_id: str) -> int:
    inv = getattr(actor, "inventory", None) or []
    return sum(getattr(it, "quantity", 1) for it in inv
              if getattr(it, "id", "") == item_id)


def _has_tool(actor, tool: str) -> bool:
    try:
        from world.gathering import has_tool
        return has_tool(actor, tool)
    except Exception:
        return any(getattr(it, "id", "") == tool
                   for it in (getattr(actor, "inventory", None) or []))


def _labor_gate(actor, labor: dict) -> Tuple[bool, str]:
    """Does `actor` meet a rule's labor requirements? (None actor = system/DM
    use — gates are skipped.)"""
    if actor is None:
        return True, ""
    tool = labor.get("tool")
    if tool and not _has_tool(actor, tool):
        return False, f"needs a {tool}"
    skill = labor.get("skill")
    min_lvl = labor.get("min_level", 0)
    if skill and min_lvl:
        try:
            from engine.skill_progression import get_skill_level
            if get_skill_level(actor, skill) < min_lvl:
                return False, f"needs {skill} {min_lvl}"
        except Exception:
            pass
    for iid, need in (labor.get("resources") or {}).items():
        if _count(actor, iid) < need:
            return False, f"needs {need} {iid}"
    return True, ""


def protected(engine, x: int, y: int) -> bool:
    """A tile inside a typed POI Location (a named settlement building / seeded
    structure) is off-limits to free mutation — reuses the DM charter's rule so
    towns and dungeons can't be griefed. Freestanding tiles are fair game."""
    try:
        for loc in engine.world.locations:
            if not (loc.properties or {}).get("type"):
                continue
            if loc.x <= x < loc.x + loc.width and \
                    loc.y <= y < loc.y + loc.height:
                return True
    except Exception:
        pass
    return False


# ---- the API --------------------------------------------------------------

def can_mutate(engine, x: int, y: int, to_t, means: str,
               actor=None) -> Tuple[bool, str]:
    """Could `means` (labor|magic) turn tile (x,y) into `to_t`? → (ok, reason)."""
    wmap = engine.world.map
    if not (0 <= x < wmap.width and 0 <= y < wmap.height):
        return False, "off the map"
    cur = wmap.get_terrain_at(x, y)
    found = rule_for(cur, to_t)
    if found is None:
        return False, f"can't turn {_tname(cur)} into {_tname(to_t)}"
    _rid, rule = found
    block = rule.get(means)
    if block is None:
        return False, f"no {means} way to {rule.get('verb', 'do that')}"
    if protected(engine, x, y):
        return False, "that ground is protected"
    # magical WARD: only a caster at least as powerful as the creator may alter a
    # magically-shaped tile; mundane labour can't touch a magic ward at all
    wards = getattr(engine, "wards", None)
    if wards is not None and actor is not None:
        wp = wards.power_at(x, y)
        if wp > 0:
            if means != "magic":
                return False, "warded by magic — mundane tools can't touch it"
            from engine.wards import caster_power
            if caster_power(actor) < wp:
                return False, "warded by a greater power"
    if wmap.characters.get((x, y)) is not None and \
            _tname(to_t) in ("water", "mountain", "building"):
        return False, "something is standing there"
    if means == "labor":
        ok, why = _labor_gate(actor, block)
        if not ok:
            return False, why
    return True, rule.get("verb", "reshape the land")


def mutate(engine, x: int, y: int, to_t, means: str, actor=None,
           charge: bool = True, quiet: bool = False) -> Tuple[bool, str]:
    """Validate → (labor) consume resources & drop by-products → set the terrain
    → beat. Magic mana is the caller's (spell) concern. Returns (ok, message)."""
    ok, reason = can_mutate(engine, x, y, to_t, means, actor)
    if not ok:
        return False, reason
    _rid, rule = rule_for(engine.world.map.get_terrain_at(x, y), to_t)
    block = rule.get(means) or {}
    if means == "labor" and charge and actor is not None:
        for iid, need in (block.get("resources") or {}).items():
            _consume(actor, iid, need)
        for iid, qty in (block.get("yields") or {}).items():
            _give(actor, iid, qty)
    tt = to_t if isinstance(to_t, TerrainType) else TerrainType(_tname(to_t))
    engine.world.map.set_terrain(x, y, tt)
    # stamp / lift the ward: MAGIC leaves a ward of the caster's power; mundane
    # LABOUR (or the system) leaves plain, unwarded ground
    wards = getattr(engine, "wards", None)
    if wards is not None:
        if means == "magic" and actor is not None:
            from engine.wards import caster_power
            wards.set(x, y, caster_power(actor))
        else:
            wards.clear(x, y)
    verb = rule.get("verb", "reshape the land")
    who = getattr(actor, "name", None)
    msg = (f"{who} works the ground to {verb} at ({x},{y})." if who
           else f"The land shifts — something moves to {verb} at ({x},{y}).")
    if not quiet:
        try:
            engine.memory_manager.add_event(f"[Build] {msg}")
        except Exception:
            pass
    return True, msg


def _consume(actor, item_id: str, n: int) -> None:
    inv = getattr(actor, "inventory", None)
    if inv is None:
        return
    left = n
    for it in list(inv):
        if getattr(it, "id", "") != item_id:
            continue
        q = getattr(it, "quantity", 1)
        take = min(q, left)
        if take >= q:
            inv.remove(it)
        else:
            it.quantity = q - take
        left -= take
        if left <= 0:
            break


def _give(actor, item_id: str, qty: int) -> None:
    try:
        from items.item_registry import create_item
        it = create_item(item_id, quantity=qty)
        if it and hasattr(actor, "add_item"):
            actor.add_item(it)
    except Exception:
        pass
