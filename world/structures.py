"""Structures (P9.1) — fantastical buildings as pure data.

A structure in `data/structures.json` is a named stack of themed
levels that attaches to an overworld location: each level is a grid
of letters (W wall, F/. floor, D door, `>` stairs down, `<` stairs
up, T/B/C/R/A/S furniture, K inscription), linked with the P9A.5
twinned-stair convention. Levels can be `dark` (the P8.6
shadowcaster runs — bring your courage), carry authored inscriptions
(E to read), and list monsters that POPULATE ON FIRST VISIT and stay
put as zone natives. Which levels have been populated persists via
save_load, so a cleared crypt stays cleared.

The Ruined Keep ships as the first structure; the temple crypt and
wizard's tower (P9.3/P9.4) are JSON away.
"""

import json
import logging
import os
from typing import Dict, List, Optional

logger = logging.getLogger("llm_rpg.structures")

CELL_FURNITURE = {"T": "Table", "B": "Bed", "C": "Chest",
                  "R": "Barrel", "A": "Anvil", "S": "Altar"}


def _load() -> Dict[str, dict]:
    try:
        with open(os.path.join("data", "structures.json")) as fp:
            data = json.load(fp)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        logger.warning("structures.json missing/corrupt")
        return {}


STRUCTURES: Dict[str, dict] = _load()


class StructureBuilder:
    def __init__(self, engine):
        self.engine = engine
        self.populated: Dict[str, List[str]] = {}

    # ------------------------------------------------------------ build

    def build(self) -> int:
        """Attach every structure to its location. Idempotent."""
        built = 0
        for sid, spec in STRUCTURES.items():
            target = spec.get("attach_to", "")
            loc = next((l for l in self.engine.world.locations
                        if target.lower() in l.name.lower()), None)
            if loc is None:
                continue
            existing = self.engine.interiors.get(loc.name)
            if existing is not None and \
                    getattr(existing, "structure_id", None) == sid:
                continue
            levels = [self._build_level(lv, sid)
                      for lv in spec.get("levels", [])]
            if not levels:
                continue
            self._link(levels, spec.get("levels", []))
            levels[0].ground = True
            self.engine.interiors[loc.name] = levels[0]
            built += 1
        return built

    def _build_level(self, spec: dict, sid: str):
        from world.interiors import Interior
        from world.world_map import TerrainType
        rows = spec.get("grid", [])
        h, w = len(rows), max(len(r) for r in rows)
        inter = Interior(name=spec.get("name", sid),
                         width=w, height=h, ground=False,
                         description=spec.get("description", ""))
        inter.terrain = [[TerrainType.GRASS for _ in range(w)]
                         for _ in range(h)]
        inter.door = (w // 2, h - 1)
        inscriptions = list(spec.get("inscriptions", []))
        for y, row in enumerate(rows):
            for x, cell in enumerate(row.ljust(w, "W")):
                if cell == "W":
                    inter.terrain[y][x] = TerrainType.BUILDING
                elif cell == "D":
                    inter.terrain[y][x] = TerrainType.ROAD
                    inter.door = (x, y)
                elif cell == ">":
                    inter.stairs_down = (x, y)
                    inter.furniture.append(
                        {"name": "Stairs down", "x": x, "y": y})
                elif cell == "<":
                    inter.stairs_up = (x, y)
                    inter.furniture.append(
                        {"name": "Stairs up", "x": x, "y": y})
                elif cell == "K":
                    text = inscriptions.pop(0) if inscriptions else \
                        "The carving is too worn to read."
                    inter.furniture.append(
                        {"name": "Inscription", "x": x, "y": y,
                         "text": text})
                elif cell in CELL_FURNITURE:
                    inter.furniture.append(
                        {"name": CELL_FURNITURE[cell], "x": x, "y": y})
        inter.dark = bool(spec.get("dark", False))
        inter.structure_id = sid
        inter.spawns = list(spec.get("monsters", []))
        return inter

    def _link(self, levels, specs) -> None:
        for i in range(1, len(levels)):
            prev, cur = levels[i - 1], levels[i]
            if specs[i].get("position", "below") == "above":
                prev.level_above = cur
                cur.level_below = prev
            else:
                prev.level_below = cur
                cur.level_above = prev

    # -------------------------------------------------------- populate

    def on_enter_level(self, zone) -> int:
        """First visit wakes the level's monsters (zone natives)."""
        sid = getattr(zone, "structure_id", None)
        if sid is None:
            return 0
        done = self.populated.setdefault(sid, [])
        if zone.name in done:
            return 0
        done.append(zone.name)
        spawned = 0
        from world.monsters import build_monster
        for spawn in getattr(zone, "spawns", []):
            npc = build_monster(spawn.get("template", "goblin"),
                                tuple(spawn.get("at", (2, 2))))
            npc.metadata["zone"] = zone.name
            self.engine.npc_manager.add_npc(npc)
            spawned += 1
        if spawned:
            self.engine.memory_manager.add_event(
                "Something stirs in the dark ahead...")
        return spawned

    # ------------------------------------------------------ persistence

    def to_dict(self) -> dict:
        return {"populated": {k: list(v)
                              for k, v in self.populated.items()}}

    def from_dict(self, data: dict) -> None:
        self.populated = {k: list(v) for k, v in
                          data.get("populated", {}).items()}
