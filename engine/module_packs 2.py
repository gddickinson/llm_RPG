"""Module packs (P1.4) — authored campaign packs as plain data.

A pack is a dm_modules adventure module saved as JSON in
`data/module_packs/` and shipped with the game (unlike the gitignored
Legendarium). Packs install at new-game start through the same atomic
prevalidate → install → rollback pipeline the DM uses, with two
authored-content courtesies: definitions that already exist (inherited
from the Legendarium or an earlier campaign this session) are skipped
rather than refused, and installation never consumes the DM's daily
mutation budget.

World-agnostic placement: because maps are procedurally generated, a
spawn or placement may give {"anchor": "wilderness"} instead of a
"position"; the loader resolves it to an open tile far from the player.

Override the folder with env `LLM_RPG_MODULE_PACKS` (tests use tmp dirs).
"""

import glob
import json
import logging
import os
from typing import List, Optional, Tuple

logger = logging.getLogger("llm_rpg.module_packs")

MIN_ANCHOR_DISTANCE = 12          # tiles from the player (charter is 6)
_OPEN_TERRAIN = ("grass", "forest", "swamp")


def packs_root() -> str:
    return os.environ.get("LLM_RPG_MODULE_PACKS",
                          os.path.join("data", "module_packs"))


def discover_packs() -> List[dict]:
    """All readable packs, sorted by filename (install order)."""
    packs = []
    for path in sorted(glob.glob(os.path.join(packs_root(), "*.json"))):
        try:
            with open(path) as fp:
                pack = json.load(fp)
            if isinstance(pack, dict):
                packs.append(pack)
            else:
                logger.warning(f"pack {path} is not an object; skipped")
        except (OSError, json.JSONDecodeError) as e:
            logger.warning(f"pack {path} unreadable; skipped: {e}")
    return packs


def _open_spot(engine, used: set) -> Optional[Tuple[int, int]]:
    """An unoccupied open-terrain tile far from the player."""
    wmap = engine.world.map
    px, py = engine.player.position
    for y in range(1, wmap.height - 1, 2):
        for x in range(1, wmap.width - 1, 2):
            if (x, y) in used:
                continue
            if abs(x - px) + abs(y - py) < MIN_ANCHOR_DISTANCE:
                continue
            try:
                if wmap.get_terrain_at(x, y).value not in _OPEN_TERRAIN:
                    continue
                if wmap.get_character_at(x, y) is not None:
                    continue
            except Exception:
                continue
            used.add((x, y))
            return (x, y)
    return None


def _resolve_anchors(engine, pack: dict) -> dict:
    """Copy of the pack with every anchor turned into a position."""
    module = dict(pack)
    used = set()
    for key in ("spawns", "placements"):
        entries = []
        for entry in pack.get(key, []):
            entry = dict(entry)
            if "position" not in entry and \
                    entry.get("anchor") == "wilderness":
                spot = _open_spot(engine, used)
                if spot is None:
                    logger.warning(f"pack {pack.get('module_id')}: no "
                                   f"open tile for {key} anchor; dropped")
                    continue
                entry["position"] = list(spot)
                entry.pop("anchor", None)
            entries.append(entry)
        if entries or key in pack:
            module[key] = entries
    return module


def _skip_inherited(module: dict) -> dict:
    """Drop definitions the world already knows (Legendarium or an
    earlier campaign this session) — the pack still spawns/quests."""
    from world.monsters import MONSTER_TEMPLATES
    from items.item_registry import ITEM_REGISTRY
    module = dict(module)
    module["monsters"] = {
        tid: spec for tid, spec in module.get("monsters", {}).items()
        if tid not in MONSTER_TEMPLATES}
    module["items"] = {
        iid: spec for iid, spec in module.get("items", {}).items()
        if iid not in ITEM_REGISTRY}
    return module


def _install_structures(engine, pack) -> int:
    """P14.2b: packs ship whole structures. Each spec goes through
    the DM charter (define_structure: level/grid/monster/value caps)
    but costs no budget — authored content is free. Already-known
    ids (the Legendarium loaded them from an earlier campaign) skip
    silently; a refused spec is logged, never fatal to the pack."""
    from world.structures import STRUCTURES
    placed = 0
    for sid, spec in pack.get("structures", {}).items():
        if sid in STRUCTURES:
            continue
        spent_before = dict(engine.dm._spent)
        ok, note = engine.dm.define_structure(sid, spec)
        engine.dm._spent = spent_before
        if ok:
            placed += 1
        else:
            logger.warning(f"pack structure '{sid}' refused: {note}")
    return placed


def install_packs(engine) -> int:
    """Install every pack at new-game start. Returns how many landed."""
    from engine.dm_modules import install_module
    installed = 0
    for pack in discover_packs():
        module = _skip_inherited(_resolve_anchors(engine, pack))
        placed = _install_structures(engine, pack)
        note = ""                            # bug-fix: a structures-only pack
        if any(module.get(k) for k in ("monsters", "items", "spawns",
                                       "placements", "quests",
                                       "beats")):
            spent_before = dict(engine.dm._spent)
            ok, note = install_module(engine, module)
            engine.dm._spent = spent_before  # authored content is free
        else:
            ok = placed > 0                  # a structures-only pack
            note = note or "no structures placed"
        if ok:
            installed += 1
            engine.memory_manager.add_event(
                f"[Module] '{module.get('title')}' shapes this campaign.")
        else:
            logger.warning(f"pack refused: {note}")
    return installed
