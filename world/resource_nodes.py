"""Depletable, regrowing resource nodes (P16.4).

Ports autonomous_world's resource tiles (`leaves_tile` +
`forest_regrowth`) onto our fixed grid: a NODE sits on a matching
terrain tile with a handful of CHARGES, and working it (chopping a
grove, in this first cut) spends one. When a node runs dry it
TRANSFORMS the tile — a felled grove becomes grass — which naturally
takes it out of the gathering pool (grass is no longer a woodcutting
node), so a stretch of forest can be logged out. Then the land heals:
after `regrow_days` the ground returns and the charges refill.

This makes gathering a finite-but-renewable, destructible-tile
interaction (composing with the terrain grid and P10.2) and gives
P16.1's raw sources a place on the map that can be exhausted and
recover. The kinds are data (`data/resource_nodes.json`) — this first
round seeds and wires GROVES; ore veins and herb patches are a config
addition. State persists.
"""

import logging
import random
from typing import Dict, Optional

from items.data_loader import load_data_file
from world.world_map import TerrainType

logger = logging.getLogger("llm_rpg.resource_nodes")

SPECS: Dict[str, dict] = load_data_file("resource_nodes.json") or {}
SPECS = {k: v for k, v in SPECS.items() if not k.startswith("_")}
SEED_FRACTION = 0.12        # of matching tiles that become nodes


class ResourceNodeSystem:
    def __init__(self, engine, seed: int = None):
        self.engine = engine
        self.rng = random.Random(seed)
        # (x, y) -> {"kind", "charges", "max", "regrow_day"}
        self.nodes: Dict[tuple, dict] = {}

    def _day(self) -> int:
        return self.engine.world.time // (24 * 60)

    # ---- world-start seeding ---------------------------------------

    def seed(self) -> int:
        """Scatter nodes across a fraction of their matching terrain.
        Idempotent — a no-op once seeded (or rehydrated from a save)."""
        if self.nodes:
            return 0
        by_terrain = {}
        for kind, spec in SPECS.items():
            by_terrain.setdefault(spec.get("terrain"), kind)
        wmap = self.engine.world.map
        made = 0
        for y in range(wmap.height):
            for x in range(wmap.width):
                kind = by_terrain.get(wmap.terrain[y][x].value)
                if kind and self.rng.random() < SEED_FRACTION:
                    ch = SPECS[kind].get("charges", 4)
                    self.nodes[(x, y)] = {"kind": kind, "charges": ch,
                                          "max": ch, "regrow_day": None}
                    made += 1
        return made

    # ---- queries ---------------------------------------------------

    def node_at(self, x: int, y: int) -> Optional[dict]:
        return self.nodes.get((x, y))

    def live_at(self, x: int, y: int, skill_id: str = None) -> bool:
        n = self.nodes.get((x, y))
        if not n or n["charges"] <= 0:
            return False
        return skill_id is None or SPECS.get(n["kind"], {}).get(
            "skill") == skill_id

    # ---- harvest & regrowth ----------------------------------------

    def harvest(self, x: int, y: int, skill_id: str) -> bool:
        """Spend one charge of a live, matching node here. On the last
        charge the tile is transformed (leaves_tile). Returns whether a
        charge was spent."""
        n = self.nodes.get((x, y))
        if not n or n["charges"] <= 0:
            return False
        if SPECS.get(n["kind"], {}).get("skill") != skill_id:
            return False
        n["charges"] -= 1
        if n["charges"] <= 0:
            self._deplete(x, y, n)
        return True

    def _deplete(self, x: int, y: int, node: dict) -> None:
        spec = SPECS.get(node["kind"], {})
        self._set_terrain(x, y, spec.get("leaves_tile"))
        node["regrow_day"] = self._day() + spec.get("regrow_days", 7)
        self.engine.memory_manager.add_event(
            "[Realm] A stand of woodland is logged out; only stumps "
            "remain.")

    def run_day(self) -> int:
        """Regrow every node whose rest is up: the ground returns and the
        charges refill. Returns how many regrew."""
        day = self._day()
        regrew = 0
        for (x, y), n in self.nodes.items():
            if n["charges"] <= 0 and n["regrow_day"] is not None \
                    and day >= n["regrow_day"]:
                self._set_terrain(x, y, SPECS.get(n["kind"], {}).get(
                    "terrain"))
                n["charges"] = n["max"]
                n["regrow_day"] = None
                regrew += 1
        return regrew

    def _set_terrain(self, x: int, y: int, terrain_value) -> None:
        if not terrain_value:
            return
        try:
            self.engine.world.map.terrain[y][x] = TerrainType(terrain_value)
        except Exception as e:                           # pragma: no cover
            logger.debug(f"terrain swap {terrain_value}: {e}")

    # ---- persistence -----------------------------------------------

    def to_dict(self) -> dict:
        return {"nodes": {f"{x},{y}": dict(v)
                          for (x, y), v in self.nodes.items()}}

    def from_dict(self, d: dict) -> None:
        self.nodes = {}
        for key, v in (d or {}).get("nodes", {}).items():
            try:
                x, y = (int(p) for p in key.split(","))
                self.nodes[(x, y)] = v
            except Exception:
                continue
