"""LIVING_WORLD C3 — visible TRIBE CAMPS (the marquee of Area C).

The audit: a monster tribe was an ABSTRACT `strength` int that raided nightly and
only ever spilled a combat raid-party onto the map — you never met the tribe "at
home". This plants a visible CAMP for each tribe near its territory, seated with a
role-tagged CAST — a CHIEF at the totem, WARRIORS (sentries) on watch, FORAGERS,
and a SHAMAN — so a tribe reads as a lived community you can find, scout, and take
on. The members reuse the C1 lair-role behaviour (`territorial` leash + `lair_role`
→ `heuristic._hostile_action` paces the sentries / holds the chief), and are tagged
`lair:tribe:<tid>` so the P19.3 pack brain bands them under their champion when you
close in. Camp size scales with the tribe's `strength`. Persists like the lairs.
"""

import logging
import random
from typing import Dict, List, Optional, Tuple

from world.world_map import TerrainType

logger = logging.getLogger("llm_rpg.tribe_camps")

CAMP_HOME_RADIUS = 7          # a camp is a touch wider than a lair den
MIN_DIST_FROM_START = 22      # a war-camp is not a starting-meadow sight
MIN_CAMP_GAP = 20            # camps don't crowd each other
MAX_WARRIORS = 4             # a camp is chief + shaman + forager + up to this many

# where a camp's folk can stand
WALKABLE = {TerrainType.GRASS, TerrainType.FOREST, TerrainType.ROAD,
            TerrainType.BRIDGE, TerrainType.SWAMP}
# a tribe's `terrain` affinity → the terrain its camp nestles beside
_AFFINITY = {"forest": TerrainType.FOREST, "swamp": TerrainType.SWAMP,
             "mountains": TerrainType.MOUNTAIN, "mountain": TerrainType.MOUNTAIN,
             "grass": TerrainType.GRASS}


class TribeCampSystem:
    def __init__(self, engine, seed: int = None):
        self.engine = engine
        self.rng = random.Random(seed)
        self.camps: List[dict] = []          # [{tid,name,pos,members:[ids]}]
        self._seeded = False

    # ---------------------------------------------------------------- seed
    def seed(self) -> int:
        if self._seeded:
            return 0
        self._seeded = True
        tribes = self.engine.monster_tribes
        try:
            tribes._ensure()
            specs = tribes._tribes()
        except Exception as e:
            logger.debug(f"tribe camps: no tribes ({e})")
            return 0
        n = 0
        for tid, spec in specs.items():
            if self._plant_camp(tid, spec, tribes.strength.get(tid, 20)):
                n += 1
        logger.info(f"Tribe camps: planted {n}")
        return n

    def _plant_camp(self, tid: str, spec: dict, strength: int) -> bool:
        site = self._find_site(spec.get("terrain", "forest"))
        if site is None:
            return False
        cx, cy = site
        crew = self._compose(spec, strength)
        ring = self._free_ring(cx, cy, len(crew))
        if len(ring) < len(crew):
            return False
        from world.monsters import build_monster
        members = []
        for (template, role), pos in zip(crew, ring):
            try:
                m = build_monster(template, pos)
            except Exception:
                continue
            md = m.metadata
            md["tribe"] = tid
            md["camp_member"] = True          # a seated resident, NOT a raid-spiller
            md["lair"] = f"tribe:{tid}"       # bands via the P19.3 pack brain
            md["home_pos"] = [cx, cy]
            md.setdefault("behavior", {})["territorial"] = CAMP_HOME_RADIUS
            md["lair_role"] = role
            self.engine.npc_manager.add_npc(m)
            self.engine.world.map.place_character(m, *pos)
            members.append(m.id)
        if not members:
            return False
        self._mark(spec, cx, cy, tid)
        self.camps.append({"tid": tid, "name": spec.get("name", tid),
                           "pos": [cx, cy], "members": members})
        try:
            self.engine.memory_manager.add_event(
                f"[Realm] {spec.get('name', 'A wild tribe')} has a camp in the "
                f"{spec.get('terrain', 'wilds')}.")
        except Exception:
            pass
        return True

    def _compose(self, spec: dict, strength: int) -> List[Tuple[str, str]]:
        """The camp's cast (template, role), scaled by strength: a chief + a
        shaman + a forager + a band of warriors (some sentries, some guards)."""
        champ = spec.get("champion", "bandit")
        raider = spec.get("raider", "goblin")
        crew: List[Tuple[str, str]] = [(champ, "chief"), (raider, "shaman"),
                                       (raider, "forager")]
        warriors = min(MAX_WARRIORS, 2 + strength // 25)
        for i in range(warriors):
            crew.append((raider, "sentry" if i % 2 == 0 else "guard"))
        return crew

    # ---------------------------------------------------------------- siting
    def _find_site(self, affinity: str) -> Optional[Tuple[int, int]]:
        wmap = self.engine.world.map
        want = _AFFINITY.get(affinity, TerrainType.FOREST)
        px, py = self.engine.player.position if self.engine.player else (0, 0)
        best = None
        for _ in range(400):
            x = self.rng.randint(3, wmap.width - 4)
            y = self.rng.randint(3, wmap.height - 4)
            if wmap.terrain[y][x] not in WALKABLE:
                continue
            if abs(x - px) + abs(y - py) < MIN_DIST_FROM_START:
                continue
            if any(abs(x - c["pos"][0]) + abs(y - c["pos"][1]) < MIN_CAMP_GAP
                   for c in self.camps):
                continue
            if not self._near(wmap, x, y, want, 4):
                continue
            if (x, y) in wmap.characters:
                continue
            best = (x, y)
            break
        return best

    @staticmethod
    def _near(wmap, x, y, want, r) -> bool:
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                nx, ny = x + dx, y + dy
                if 0 <= nx < wmap.width and 0 <= ny < wmap.height and \
                        wmap.terrain[ny][nx] == want:
                    return True
        return False

    def _free_ring(self, cx: int, cy: int, needed: int) -> List[Tuple[int, int]]:
        wmap = self.engine.world.map
        out: List[Tuple[int, int]] = []
        for r in range(1, 6):
            for dy in range(-r, r + 1):
                for dx in range(-r, r + 1):
                    if max(abs(dx), abs(dy)) != r:
                        continue
                    x, y = cx + dx, cy + dy
                    if not (0 <= x < wmap.width and 0 <= y < wmap.height):
                        continue
                    if wmap.terrain[y][x] not in WALKABLE or \
                            (x, y) in wmap.characters:
                        continue
                    out.append((x, y))
                    if len(out) >= needed:
                        return out
        return out

    def _mark(self, spec: dict, cx: int, cy: int, tid: str) -> None:
        try:
            from world.location import Location
            loc = Location(f"{spec.get('name', 'Tribe')} Camp",
                           f"A wild tribe's camp. {spec.get('name', '')}",
                           cx, cy, 1, 1)
            loc.add_property("tribe_camp", tid)
            self.engine.world.add_location(loc)
        except Exception as e:
            logger.debug(f"camp marker: {e}")

    # ---------------------------------------------------------------- query
    def roster(self, tid: str) -> List:
        for c in self.camps:
            if c["tid"] == tid:
                return [self.engine.npc_manager.npcs.get(i)
                        for i in c["members"]
                        if i in self.engine.npc_manager.npcs]
        return []

    def camp_at(self, pos) -> Optional[dict]:
        for c in self.camps:
            if abs(c["pos"][0] - pos[0]) + abs(c["pos"][1] - pos[1]) <= 1:
                return c
        return None

    def has_camp(self, tid: str) -> bool:
        return any(c["tid"] == tid for c in self.camps)

    def camp_name(self, tid: str) -> Optional[str]:
        for c in self.camps:
            if c["tid"] == tid:
                return c["name"]
        return None

    def living_warriors(self, tid: str) -> int:
        """C3: how many of a camp's fighters still stand — a raid draws its
        warband from here, so a scouted-and-thinned camp sends fewer raiders."""
        fighters = ("chief", "sentry", "guard")
        n = 0
        for c in self.camps:
            if c["tid"] != tid:
                continue
            for i in c["members"]:
                m = self.engine.npc_manager.npcs.get(i)
                if m and m.is_alive() and \
                        (m.metadata or {}).get("lair_role") in fighters:
                    n += 1
        return n

    # ---------------------------------------------------------------- persist
    def to_dict(self) -> dict:
        return {"seeded": self._seeded, "camps": self.camps}

    def from_dict(self, d: dict) -> None:
        if not d:
            return
        self._seeded = d.get("seeded", False)
        self.camps = d.get("camps", [])
