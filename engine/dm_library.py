"""The Legendarium — the persistent generative library (P6.7, George's
design): the game gets permanently richer every time it's played.

Everything the DM defines is written to `data/dm_library/` (gitignored,
like saves) with provenance stamps, and loaded into the runtime
registries at every startup — so a monster invented for tonight's
adventure joins the world's bestiary for every future campaign.

Retired entities keep their stories: when a DM-created monster falls,
it enters `legendarium.json` with who slew it and when. The DM digest
carries the legendarium tail, so any future DM can resurface the past
("the blade thought lost in the Murkfen turns up in a fence's stock").

Curation: dedup by id, size caps, corrupt files skipped not fatal.
Override the root with env `LLM_RPG_DM_LIBRARY` (tests use tmp dirs).
"""

import json
import logging
import os
from datetime import date
from typing import Dict, List

logger = logging.getLogger("llm_rpg.dm_library")

LIBRARY_CAP = 100        # per kind (monsters / items)
LEGENDARIUM_CAP = 200


def library_root() -> str:
    return os.environ.get("LLM_RPG_DM_LIBRARY",
                          os.path.join("data", "dm_library"))


def _path(name: str) -> str:
    return os.path.join(library_root(), name)


def _load_file(name: str) -> Dict:
    try:
        with open(_path(name)) as fp:
            data = json.load(fp)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _save_file(name: str, data) -> None:
    try:
        os.makedirs(library_root(), exist_ok=True)
        tmp = _path(name) + ".tmp"
        with open(tmp, "w") as fp:
            json.dump(data, fp, indent=2)
        os.replace(tmp, _path(name))
    except OSError as e:
        logger.warning(f"library write failed: {e}")


# ---- recording definitions ---------------------------------------------

def record_definition(kind: str, def_id: str, spec: dict,
                      day: int) -> bool:
    """kind: 'monsters' | 'items'. Returns True if newly recorded."""
    name = f"{kind}.json"
    library = _load_file(name)
    if def_id in library:
        return False
    if len(library) >= LIBRARY_CAP:
        logger.info(f"library {kind} at cap; not recording {def_id}")
        return False
    library[def_id] = {
        "spec": dict(spec),
        "provenance": {"day": day, "date": date.today().isoformat()},
    }
    _save_file(name, library)
    return True


# ---- loading at startup ----------------------------------------------------

def load_into_registries() -> int:
    """Merge library definitions into the runtime registries. Returns
    how many entries were inherited."""
    from world.monsters import MONSTER_TEMPLATES
    from items.item_registry import ITEM_REGISTRY
    from items.item import Item
    inherited = 0
    for tid, entry in _load_file("monsters.json").items():
        spec = entry.get("spec", {})
        if tid not in MONSTER_TEMPLATES and spec.get("name"):
            MONSTER_TEMPLATES[tid] = dict(spec)
            inherited += 1
    for iid, entry in _load_file("items.json").items():
        spec = dict(entry.get("spec", {}))
        spec.setdefault("id", iid)
        if iid in ITEM_REGISTRY:
            continue
        try:
            ITEM_REGISTRY[iid] = Item.from_dict(spec)
            inherited += 1
        except Exception:
            logger.warning(f"library item '{iid}' unloadable; skipped")
    try:
        from world.structures import STRUCTURES
        for sid, entry in _load_file("structures.json").items():
            spec = entry.get("spec", {})
            if sid not in STRUCTURES and spec.get("levels"):
                STRUCTURES[sid] = dict(spec)
                inherited += 1
    except Exception:
        pass
    if inherited:
        logger.info(f"Legendarium: inherited {inherited} definitions")
    return inherited


# ---- the legendarium (retired entities) ---------------------------------------

def record_legend(entry: dict) -> None:
    """entry: {name, kind, story, slain_by, day}."""
    data = _load_file("legendarium.json")
    legends = data.get("legends", [])
    legends.append({**entry, "date": date.today().isoformat()})
    del legends[:-LEGENDARIUM_CAP]
    _save_file("legendarium.json", {"legends": legends})


def legendarium_tail(k: int = 5) -> List[dict]:
    return _load_file("legendarium.json").get("legends", [])[-k:]
