"""Overworld monster lairs (P19.2).

A lair is a named danger planted on the overworld at world start: a
dragon's roost on a mountain shoulder, a goblin warren in the forest, a
troll den by the fens. Each holds a boss or a pack over a hoard. Kill
everything that lives there and the hoard spills onto the ground, a
`[Legend]` line marks the deed, gold fills your purse, and the place
falls quiet for good.

A lair sits on the OVERWORLD, not in a zone — which matters: an apex
there gets its full kit, because the P19.1 breath telegraph only paints
while `active_zone()` is None. A roost is where you finally face a dragon
breathing fire and scorching the ground you stand on.

Content-as-data: archetypes live in `data/lairs.json` (occupants + hoard
+ a `near` terrain affinity + a legend line). Seeded away from
settlements and the player's start; state persists across saves.
"""

import logging
import random
from typing import Dict, List, Optional, Tuple

from world.world_map import TerrainType

logger = logging.getLogger("llm_rpg.lairs")

MAX_LAIRS = 3
MIN_DIST_FROM_START = 18       # a dragon is not a starting-meadow encounter
SEARCH_RADIUS = 6              # rings scanned to seat a lair's occupants

# where a lair's creatures can stand (fliers still perch on these)
WALKABLE = {TerrainType.GRASS, TerrainType.FOREST, TerrainType.ROAD,
            TerrainType.BRIDGE, TerrainType.SWAMP, TerrainType.FARMLAND}

_NEAR = {"mountain": TerrainType.MOUNTAIN, "forest": TerrainType.FOREST,
         "swamp": TerrainType.WATER, "water": TerrainType.WATER,
         "cave": TerrainType.CAVE}


class LairSystem:
    def __init__(self, engine, seed: int = None):
        self.engine = engine
        self.rng = random.Random(seed)
        self.lairs: List[dict] = []
        self._seeded = False

    # ---- data ------------------------------------------------------

    def _archetypes(self) -> Dict[str, dict]:
        from items.data_loader import load_data_file
        try:
            return load_data_file("lairs.json")
        except Exception as e:
            logger.debug(f"lairs.json: {e}")
            return {}

    # ---- seeding ---------------------------------------------------

    def seed(self) -> int:
        """Plant up to one of each archetype where a site fits."""
        if self._seeded or self.lairs:
            return 0
        self._seeded = True
        arche = self._archetypes()
        placed = 0
        for key in sorted(arche.keys()):
            if placed >= MAX_LAIRS:
                break
            site = self._find_site(arche[key])
            if site is None:
                continue
            if self._place_lair(key, arche[key], site):
                placed += 1
        if placed:
            logger.info(f"Seeded {placed} overworld lair(s).")
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

    def _find_site(self, spec: dict) -> Optional[Tuple[int, int]]:
        wmap = self.engine.world.map
        near_t = self._terrain(spec.get("near"))
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
                if near_t is not None and not self._has_near(x, y, near_t, 3):
                    continue
                cands.append((x, y))
        return self.rng.choice(cands) if cands else None

    def _free_ring(self, cx: int, cy: int, needed: int) -> List[Tuple[int, int]]:
        wmap = self.engine.world.map
        out = []
        for r in range(0, SEARCH_RADIUS + 1):
            for dy in range(-r, r + 1):
                for dx in range(-r, r + 1):
                    if max(abs(dx), abs(dy)) != r:
                        continue                   # only the ring at radius r
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

    def _place_lair(self, key: str, spec: dict, center) -> bool:
        from world.monsters import build_monster
        cx, cy = center
        need = sum(g.get("count", 1) for g in spec.get("occupants", []))
        ring = self._free_ring(cx, cy, need)
        occ_ids, ri = [], 0
        for grp in spec.get("occupants", []):
            for _ in range(grp.get("count", 1)):
                if ri >= len(ring):
                    break
                pos = ring[ri]
                ri += 1
                m = build_monster(grp["template"], pos)
                m.metadata["lair"] = key
                m.metadata["home_pos"] = list(pos)
                self.engine.npc_manager.add_npc(m)
                self.engine.world.map.place_character(m, *pos)
                occ_ids.append(m.id)
        if not occ_ids:
            return False
        self._mark(spec, cx, cy, key)
        self.lairs.append({
            "key": key, "name": spec["name"], "pos": [cx, cy],
            "occupants": occ_ids, "hoard": list(spec.get("hoard", [])),
            "gold": spec.get("gold", 0), "legend": spec.get("legend", ""),
            "cleared": False,
        })
        return True

    def _mark(self, spec: dict, cx: int, cy: int, key: str) -> None:
        """A named marker on the map so the lair reads as a place."""
        try:
            from world.location import Location
            loc = Location(spec["name"],
                           f"A monster lair. {spec.get('legend', '')}",
                           cx, cy, 1, 1)
            loc.add_property("lair", key)
            self.engine.world.add_location(loc)
        except Exception as e:
            logger.debug(f"Lair marker: {e}")

    # ---- clearing --------------------------------------------------

    def check_cleared(self) -> int:
        """Clear-detection: when a lair's last defender falls, the hoard
        is yours. Cheap — a handful of id lookups per turn."""
        n = 0
        for lair in self.lairs:
            if lair.get("cleared"):
                continue
            if self._all_dead(lair["occupants"]):
                self._reward(lair)
                lair["cleared"] = True
                n += 1
        return n

    def _all_dead(self, ids: List[str]) -> bool:
        npcs = self.engine.npc_manager.npcs
        for oid in ids:
            n = npcs.get(oid)
            if n is not None and n.is_active():
                return False
        return True

    def _reward(self, lair: dict) -> None:
        from items.item_registry import create_item
        cx, cy = lair["pos"]
        for iid in lair.get("hoard", []):
            it = create_item(iid)
            if it is not None:
                self.engine.world.add_item_to_ground(it, cx, cy)
        gold = lair.get("gold", 0)
        if gold:
            try:
                self.engine.player.gold += gold
            except Exception:
                pass
        self.engine.memory_manager.add_event(f"[Legend] {lair['legend']}")
        if gold or lair.get("hoard"):
            self.engine.memory_manager.add_event(
                f"The hoard of the {lair['name']} is yours"
                + (f" — {gold} gold and its treasures." if gold else "."))

    def cleared_count(self) -> int:
        return sum(1 for l in self.lairs if l.get("cleared"))

    # ---- persistence -----------------------------------------------

    def to_dict(self) -> dict:
        return {"lairs": self.lairs, "seeded": self._seeded}

    def from_dict(self, d: dict) -> None:
        d = d or {}
        self.lairs = d.get("lairs", []) or []
        self._seeded = d.get("seeded", bool(self.lairs))
