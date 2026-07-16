"""P28.2d — a STABLE beside the start town, so a rider can actually get a mount.

The data-driven mount roster (`engine/mounts.py`) sells horses/mules "at a
stable" (`sold_at`), but no stable `Location` was ever seeded — so there was
nowhere to buy one and the whole feature never surfaced (George). This plants a
`Stable` marker beside each settlement at world start, like the guild halls; the
E-key opens the stable menu (`ui/stable_panel`) when you stand at one. Persists.
"""

import logging
from typing import List, Optional, Tuple

from world.world_map import TerrainType

logger = logging.getLogger("llm_rpg.stables")

_WALKABLE = {TerrainType.GRASS, TerrainType.ROAD, TerrainType.BRIDGE,
             TerrainType.FARMLAND}


class StableSystem:
    def __init__(self, engine):
        self.engine = engine
        self.stables: List[dict] = []
        self._seeded = False

    def seed(self) -> int:
        if self._seeded or self.stables:
            return 0
        self._seeded = True
        placed = 0
        for loc in self._settlements():
            spot = self._walkable_near(loc.x, loc.y)
            if spot is not None:
                self._plant(loc.name, spot)
                placed += 1
        if placed:
            logger.info(f"Seeded {placed} stable(s).")
        return placed

    def _settlements(self) -> list:
        locs = getattr(self.engine.world, "locations", []) or []
        out, seen = [], set()
        for l in locs:
            if l.get_property("kind"):        # a town BUILDING, not a settlement
                continue
            n = (l.name or "").lower()
            is_settlement = l.get_property("town") or \
                any(w in n for w in ("village", "hamlet", " town"))
            if is_settlement and "stable" not in n and l.name not in seen:
                out.append(l)
                seen.add(l.name)
        if out:
            return out
        return [l for l in locs if "oakvale" in (l.name or "").lower()][:1]

    def _walkable_near(self, cx: int, cy: int) -> Optional[Tuple[int, int]]:
        wmap = self.engine.world.map
        chars = getattr(wmap, "characters", {}) or {}
        for r in range(2, 9):
            for dy in range(-r, r + 1):
                for dx in range(-r, r + 1):
                    if max(abs(dx), abs(dy)) != r:
                        continue
                    x, y = cx + dx, cy + dy
                    if not (0 <= x < wmap.width and 0 <= y < wmap.height):
                        continue
                    if wmap.terrain[y][x] in _WALKABLE \
                            and (x, y) not in chars \
                            and self.engine.world.get_location_at(x, y) is None:
                        return (x, y)
        return None

    def _plant(self, settlement: str, spot: Tuple[int, int]) -> None:
        from world.location import Location
        cx, cy = spot
        name = f"{settlement.split()[0]} Stable"
        loc = Location(name, "Horses and mules for the road ahead.",
                       cx, cy, 1, 1)
        loc.add_property("type", "stable")
        self.engine.world.add_location(loc)
        self.stables.append({"name": name, "settlement": settlement,
                             "pos": [cx, cy]})
        self.engine.memory_manager.add_event(
            f"[Realm] A stable stands by {settlement} — horses and mules to hire.")

    # ---- queries ---------------------------------------------------

    def stable_at(self, pos, r: int = 2) -> Optional[dict]:
        """The stable the player is standing at (or beside), or None."""
        px, py = pos
        for s in self.stables:
            sx, sy = s["pos"]
            if abs(sx - px) <= r and abs(sy - py) <= r:
                return s
        return None

    # ---- persistence -----------------------------------------------

    def to_dict(self) -> dict:
        return {"stables": self.stables, "seeded": self._seeded}

    def from_dict(self, d: dict) -> None:
        d = d or {}
        self.stables = d.get("stables", []) or []
        self._seeded = d.get("seeded", bool(self.stables))
