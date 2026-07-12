"""Guild halls as PLACES (M.7b) — where blades and companies congregate.

The M.6 adventurers were scattered by the taverns; a guild hall gives them
a HOME the player can seek out. `GuildHallSystem.seed()` plants a named
`Location` marker — the Adventurers' Guild, the Mercenaries' Rest — beside
a settlement at world start, and the adventurers gather there instead of
just any tavern (see `AdventurerSystem._gathering_spot`). So when you want
to hire a blade (M.7) or recruit a companion (M.6), you know where to go:
the guild hall, where a `roster` of the folk currently gathered is on
offer.

Content-as-data: the halls live in `data/guildhalls.json` (name, kind,
settlement, a legend line). The Location markers ride the world save; the
system persists its own small index of them. (Remainder M.7c: board-quests
and training AT the halls.)
"""

import logging
import os
from typing import Dict, List, Optional, Tuple

from world.world_map import TerrainType

logger = logging.getLogger("llm_rpg.guildhalls")

_WALKABLE = {TerrainType.GRASS, TerrainType.ROAD, TerrainType.BRIDGE,
             TerrainType.FARMLAND, TerrainType.FOREST}


class GuildHallSystem:
    def __init__(self, engine, seed: int = None):
        self.engine = engine
        self.halls: List[dict] = []        # [{id, name, kind, pos}]
        self._seeded = False

    # ---- data ------------------------------------------------------

    def _specs(self) -> List[dict]:
        from items.data_loader import load_data_file
        try:
            return load_data_file("guildhalls.json").get("guildhalls", [])
        except Exception as e:
            logger.debug(f"guildhalls.json: {e}")
            return []

    # ---- seeding ---------------------------------------------------

    def seed(self) -> int:
        # gated with the adventurers (they gather here) so a couple of extra
        # Location markers don't perturb the general test suite
        if os.environ.get("LLM_RPG_NO_ADVENTURERS"):
            return 0
        if self._seeded or self.halls:
            return 0
        self._seeded = True
        placed = 0
        for spec in self._specs():
            spot = self._site(spec)
            if spot is None:
                continue
            self._plant(spec, spot)
            placed += 1
        if placed:
            logger.info(f"Seeded {placed} guild hall(s).")
        return placed

    def _site(self, spec: dict) -> Optional[Tuple[int, int]]:
        """A walkable tile beside the settlement's tavern (or the town), not
        on another location's footprint."""
        home = spec.get("settlement", "")
        locs = getattr(self.engine.world, "locations", [])
        taverns = [l for l in locs
                   if any(w in l.name.lower() for w in ("tavern", "inn"))
                   and home.lower() in l.name.lower()]
        anchors = taverns or [l for l in locs
                              if home.lower() in l.name.lower()] or list(locs)
        for a in anchors:
            spot = self._walkable_near(a.x, a.y)
            if spot is not None:
                return spot
        return None

    def _walkable_near(self, cx: int, cy: int) -> Optional[Tuple[int, int]]:
        wmap = self.engine.world.map
        for r in range(2, 7):
            for dy in range(-r, r + 1):
                for dx in range(-r, r + 1):
                    if max(abs(dx), abs(dy)) != r:
                        continue
                    x, y = cx + dx, cy + dy
                    if not (0 <= x < wmap.width and 0 <= y < wmap.height):
                        continue
                    if wmap.terrain[y][x] in _WALKABLE \
                            and (x, y) not in wmap.characters \
                            and self.engine.world.get_location_at(x, y) is None:
                        return (x, y)
        return None

    def _plant(self, spec: dict, spot: Tuple[int, int]) -> None:
        from world.location import Location
        cx, cy = spot
        loc = Location(spec["name"], spec.get("legend", ""), cx, cy, 1, 1)
        loc.add_property("guildhall", spec.get("kind", "adventurers"))
        self.engine.world.add_location(loc)
        self.halls.append({"id": spec["id"], "name": spec["name"],
                           "kind": spec.get("kind", "adventurers"),
                           "settlement": spec.get("settlement", ""),
                           "pos": [cx, cy]})
        self.engine.memory_manager.add_event(
            f"[Realm] The {spec['name']} keeps its doors open in the region.")

    # ---- queries ---------------------------------------------------

    def hall_spot(self, settlement: str = None,
                  kind: str = None) -> Optional[Tuple[int, int]]:
        """The gathering tile of a matching hall (for adventurer seeding)."""
        for h in self.halls:
            if settlement:
                s, hs = settlement.lower(), h.get("settlement", "").lower()
                if hs and not (hs in s or s in hs):
                    continue
            if kind and h["kind"] != kind:
                continue
            return tuple(h["pos"])
        return tuple(self.halls[0]["pos"]) if self.halls else None

    def hall_at(self, pos, r: int = 3) -> Optional[dict]:
        """The guild hall the player is standing at (within r tiles)."""
        for h in self.halls:
            hx, hy = h["pos"]
            if abs(hx - pos[0]) <= r and abs(hy - pos[1]) <= r:
                return h
        return None

    def roster(self, hall_id: str, r: int = 5) -> List:
        """The adventurers/blades gathered at a hall — recruit or hire them."""
        h = next((x for x in self.halls if x["id"] == hall_id), None)
        if h is None:
            return []
        hx, hy = h["pos"]
        out = []
        for n in self.engine.npc_manager.npcs.values():
            if getattr(n, "position", None) is None or not n.is_active():
                continue
            meta = getattr(n, "metadata", {}) or {}
            if not (meta.get("adventurer") or meta.get("seeking_party")):
                continue
            if abs(n.position[0] - hx) <= r and abs(n.position[1] - hy) <= r:
                out.append(n)
        return out

    # ---- persistence -----------------------------------------------

    def to_dict(self) -> dict:
        return {"seeded": self._seeded, "halls": self.halls}

    def from_dict(self, d: dict) -> None:
        d = d or {}
        self._seeded = d.get("seeded", bool(d.get("halls")))
        self.halls = d.get("halls", []) or []
