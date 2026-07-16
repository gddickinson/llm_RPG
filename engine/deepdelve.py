"""GX.5 The Oakvale Deepdelve — a DEEP, multi-mouth dungeon.

George: "add a deep dungeon/cave system accessible via a secret entrance in
oakvale — with other entrances/exits in the surrounding area."

`DeepdelveSystem.seed()` plants SEVERAL wilderness CAVE mouths (a forest cleft,
a mountain stair, a drowned adit) at wooded / rocky / waterside sites far from
the player's start and well apart from one another. Every mouth Location
carries `dungeon_key: "deepdelve"` + `deep_dungeon` (with `deep_levels` +
`dungeon_name`), so `game_api_mixin.enter_dungeon` resolves them ALL — and, in
GX.5b, the secret Oakvale stair — to the SAME shared, persistent, DEEP dungeon:
one layout, one cleared/looted state, however you got in. `dungeon_return_pos`
is stamped per entry, so you climb back out at whichever mouth you descended by.
A couple of guards lurk at each mouth; a starting rumor points to the delve.
(GX.5c remainder: per-mouth up-stairs so you can enter one mouth and surface at
a distant one — a true wilderness short-cut.)

Content-as-data: `data/deepdelve.json` (the shared key/name/depth + the mouth
specs). Modelled on `engine/lairs.py`; state persists across saves.
"""

import logging
import random
from typing import Dict, List, Optional, Tuple

from world.world_map import TerrainType

logger = logging.getLogger("llm_rpg.deepdelve")

MIN_DIST_FROM_START = 16       # not a starting-meadow stumble
MIN_DIST_BETWEEN = 12          # mouths spread around the region
GUARD_RING = 5                 # rings scanned to seat a mouth's guards

# a mouth is stamped onto a walkable tile with its affinity terrain nearby
WALKABLE = {TerrainType.GRASS, TerrainType.FOREST, TerrainType.ROAD,
            TerrainType.BRIDGE, TerrainType.SWAMP, TerrainType.FARMLAND}

_NEAR = {"mountain": TerrainType.MOUNTAIN, "forest": TerrainType.FOREST,
         "swamp": TerrainType.WATER, "water": TerrainType.WATER}


class DeepdelveSystem:
    def __init__(self, engine, seed: int = None):
        self.engine = engine
        self.rng = random.Random(seed)
        self.mouths: List[dict] = []
        self._seeded = False

    # ---- data ------------------------------------------------------

    def _config(self) -> dict:
        from items.data_loader import load_data_file
        try:
            return load_data_file("deepdelve.json") or {}
        except Exception as e:                       # pragma: no cover
            logger.debug(f"deepdelve.json: {e}")
            return {}

    # ---- seeding ---------------------------------------------------

    def seed(self) -> int:
        """Plant the wilderness mouths of the shared Deepdelve."""
        if self._seeded or self.mouths:
            return 0
        self._seeded = True
        cfg = self._config()
        specs = cfg.get("mouths", [])
        if not specs:
            return 0
        key = cfg.get("dungeon_key", "deepdelve")
        placed_pts: List[Tuple[int, int]] = []
        placed = 0
        for spec in specs:
            site = self._find_site(spec.get("near"), placed_pts)
            if site is None:
                continue
            if self._place_mouth(spec, cfg, key, site):
                placed_pts.append(site)
                placed += 1
        if placed:
            rumor = cfg.get("rumor")
            if rumor:
                self.engine.memory_manager.add_event(f"[Realm] {rumor}")
            logger.info(f"Seeded {placed} Deepdelve mouth(s).")
        return placed

    def _terrain(self, name) -> Optional[TerrainType]:
        return _NEAR.get(name) if name else None

    def _has_near(self, x: int, y: int, t: TerrainType, r: int) -> bool:
        wmap = self.engine.world.map
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                nx, ny = x + dx, y + dy
                if 0 <= nx < wmap.width and 0 <= ny < wmap.height \
                        and wmap.terrain[ny][nx] == t:
                    return True
        return False

    def _find_site(self, near, placed_pts) -> Optional[Tuple[int, int]]:
        wmap = self.engine.world.map
        near_t = self._terrain(near)
        px, py = self.engine.player.position
        cands = []
        for y in range(1, wmap.height - 1):
            for x in range(1, wmap.width - 1):
                if wmap.terrain[y][x] not in WALKABLE:
                    continue
                if (x, y) in wmap.characters:
                    continue
                if abs(x - px) + abs(y - py) < MIN_DIST_FROM_START:
                    continue
                if self.engine.world.get_location_at(x, y) is not None:
                    continue                       # not in a town/building
                if any(abs(x - ox) + abs(y - oy) < MIN_DIST_BETWEEN
                       for ox, oy in placed_pts):
                    continue                       # spread the mouths out
                if near_t is not None and not self._has_near(x, y, near_t, 3):
                    continue
                cands.append((x, y))
        return self.rng.choice(cands) if cands else None

    def _free_ring(self, cx, cy, needed) -> List[Tuple[int, int]]:
        wmap = self.engine.world.map
        out = []
        for r in range(1, GUARD_RING + 1):
            for dy in range(-r, r + 1):
                for dx in range(-r, r + 1):
                    if max(abs(dx), abs(dy)) != r:
                        continue
                    x, y = cx + dx, cy + dy
                    if not (0 <= x < wmap.width and 0 <= y < wmap.height):
                        continue
                    if wmap.terrain[y][x] not in WALKABLE:
                        continue
                    if (x, y) in wmap.characters:
                        continue
                    out.append((x, y))
                    if len(out) >= needed:
                        return out
        return out

    def _place_mouth(self, spec, cfg, key, site) -> bool:
        from world.location import Location
        cx, cy = site
        # Stamp the cave mouth onto the map.
        self.engine.world.map.terrain[cy][cx] = TerrainType.CAVE
        loc = Location(spec["name"],
                       f"A cave mouth into the Deepdelve. "
                       f"{spec.get('legend', '')}", cx, cy, 1, 1)
        loc.add_property("dungeon_key", key)
        loc.add_property("dungeon_name", cfg.get("dungeon_name",
                                                 "The Deepdelve"))
        loc.add_property("deep_dungeon", True)
        loc.add_property("deep_levels", int(cfg.get("deep_levels", 6)))
        loc.add_property("deepdelve_mouth", True)
        self.engine.world.add_location(loc)
        guard_ids = self._place_guards(spec, cx, cy, key)
        self.mouths.append({
            "name": spec["name"], "pos": [cx, cy], "key": key,
            "legend": spec.get("legend", ""), "guards": guard_ids,
        })
        legend = spec.get("legend")
        if legend:
            self.engine.memory_manager.add_event(f"[Legend] {legend}")
        return True

    def _place_guards(self, spec, cx, cy, key) -> List[str]:
        from world.monsters import build_monster
        need = sum(g.get("count", 1) for g in spec.get("guards", []))
        ring = self._free_ring(cx, cy, need)
        ids, ri = [], 0
        for grp in spec.get("guards", []):
            for _ in range(grp.get("count", 1)):
                if ri >= len(ring):
                    break
                pos = ring[ri]
                ri += 1
                try:
                    m = build_monster(grp["template"], pos)
                except Exception:                    # pragma: no cover
                    continue
                m.metadata["deepdelve_mouth"] = spec["name"]
                m.metadata["home_pos"] = list(pos)
                self.engine.npc_manager.add_npc(m)
                self.engine.world.map.place_character(m, *pos)
                ids.append(m.id)
        return ids

    # ---- queries ---------------------------------------------------

    def mouth_positions(self) -> List[Tuple[int, int]]:
        return [tuple(m["pos"]) for m in self.mouths]

    def is_active(self) -> bool:
        return bool(self.mouths)

    # ---- persistence -----------------------------------------------

    def to_dict(self) -> dict:
        return {"mouths": self.mouths, "seeded": self._seeded}

    def from_dict(self, d: dict) -> None:
        d = d or {}
        self.mouths = d.get("mouths", []) or []
        self._seeded = d.get("seeded", bool(self.mouths))
