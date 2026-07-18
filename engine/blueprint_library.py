"""M6 — a cross-game BLUEPRINT library: save a build design once, load it into the
build planner of ANY game (George: "save designs for other sessions and games").

Mirrors `engine/dm_library`: writes `data/dm_library/blueprints.json` (root
overridable via env `LLM_RPG_DM_LIBRARY`, gitignored, plain portable JSON — copy
the file to share a design). A blueprint is a NORMALISED pattern: a list of
`[dx, dy, terrain]` offsets from the design's own corner, so `stamp(spec, cx, cy)`
reproduces it at any cursor tile. Atomic write, deduped, capped.
"""

import json
import logging
import os
import re

from engine.dm_library import library_root      # reuse the env-overridable root

logger = logging.getLogger("llm_rpg.blueprints")
_FILE = "blueprints.json"
CAP = 60


def _path() -> str:
    return os.path.join(library_root(), _FILE)


def _load() -> dict:
    try:
        with open(_path()) as fp:
            data = json.load(fp)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _save(data) -> None:
    try:
        os.makedirs(library_root(), exist_ok=True)
        tmp = _path() + ".tmp"
        with open(tmp, "w") as fp:
            json.dump(data, fp, indent=2)
        os.replace(tmp, _path())
    except OSError as e:
        logger.warning(f"blueprint write failed: {e}")


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (name or "").lower()).strip("_")


def plan_to_spec(plan: dict, name: str) -> dict:
    """A build plan `{(x,y): terrain}` → a normalised, position-independent spec."""
    xs = [x for x, _ in plan]
    ys = [y for _, y in plan]
    ox, oy = min(xs), min(ys)
    tiles = sorted([[x - ox, y - oy, t] for (x, y), t in plan.items()])
    return {"name": name, "tiles": tiles,
            "w": max(xs) - ox + 1, "h": max(ys) - oy + 1}


def stamp(spec: dict, cx: int, cy: int) -> dict:
    """A spec → a build plan `{(x,y): terrain}` anchored at (cx, cy)."""
    return {(cx + dx, cy + dy): t for dx, dy, t in spec.get("tiles", [])}


def save_blueprint(name: str, plan: dict, date_str: str = "") -> str:
    """Record `plan` as a named blueprint. Returns a status message."""
    if not plan:
        return "Nothing planned to save."
    lib = _load()
    base = _slug(name) or f"design_{len(lib) + 1}"
    bid = base
    i = 2
    while bid in lib:
        bid = f"{base}_{i}"
        i += 1
    lib[bid] = {"spec": plan_to_spec(plan, name),
                "provenance": {"date": date_str}}
    while len(lib) > CAP:                       # drop the oldest
        lib.pop(next(iter(lib)))
    _save(lib)
    return f"Saved design '{name}' ({len(plan)} tiles)."


def list_blueprints() -> list:
    """[(bid, name, spec)] for every saved design (for the planner's load menu)."""
    return [(bid, e.get("spec", {}).get("name", bid), e.get("spec", {}))
            for bid, e in _load().items()]


def count() -> int:
    return len(_load())
