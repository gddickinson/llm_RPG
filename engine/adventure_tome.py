"""P38 — "The Sunken Tome of Vael'Zhur" adventure seeder.

Module packs ship monsters/items/quests/structures but NOT NPCs, so the
adventure's areas and cast are seeded here (the light seeder the plan called
for), the way lairs/guildhalls seed authored places at world start. `seed()`:
plants a `Location` marker for each area from `data/adventure_tome.json` (near
marsh), stamps the Drowned Vault's tile to CAVE so the `data/structures.json`
`drowned_vault` structure attaches as an enterable dungeon, and seats the custom
NPCs (Sage Ondrel, Warden Halric, Ysolde) beside their area.

Gated with the guild halls / adventurers (LLM_RPG_NO_ADVENTURERS) so the extra
markers don't perturb the general suite. State (placed areas + npc ids) persists.
"""

import logging
import os
from typing import Dict, List, Optional, Tuple

from world.world_map import TerrainType

logger = logging.getLogger("llm_rpg.adventure_tome")

_BAD = (TerrainType.BUILDING, TerrainType.WATER, TerrainType.MOUNTAIN)
MIN_DIST = 14              # tiles from the player start


class AdventureTome:
    def __init__(self, engine, seed: int = None):
        self.engine = engine
        self.areas: List[dict] = []        # [{id, name, pos}]
        self.npc_ids: List[str] = []
        self._seeded = False

    # ---- data ------------------------------------------------------

    def _data(self) -> dict:
        from items.data_loader import load_data_file
        try:
            return load_data_file("adventure_tome.json") or {}
        except Exception as e:
            logger.debug(f"adventure_tome.json: {e}")
            return {}

    # ---- seeding ---------------------------------------------------

    def seed(self) -> int:
        if os.environ.get("LLM_RPG_NO_ADVENTURERS"):
            return 0
        if self._seeded or self.areas:
            return 0
        self._seeded = True
        data = self._data()
        used: set = set()
        for spec in data.get("areas", []):
            spot = self._spot(spec.get("near", "swamp"), used)
            if spot is None:
                continue
            used.add(spot)
            self._plant_area(spec, spot)
        # attach the Drowned Vault structure to its freshly-planted Location
        try:
            self.engine.structures.build()
        except Exception as e:
            logger.debug(f"vault attach: {e}")
        self._seat_npcs(data.get("npcs", {}))
        if self.areas:
            logger.info(f"Seeded the Sunken Tome adventure: "
                        f"{len(self.areas)} areas, {len(self.npc_ids)} NPCs.")
        return len(self.areas)

    def _spot(self, near: str, used: set) -> Optional[Tuple[int, int]]:
        """An open tile of (or beside) `near` terrain, far from the player and
        from other areas."""
        wmap = self.engine.world.map
        try:
            px, py = self.engine.player.position
        except Exception:
            px, py = wmap.width // 2, wmap.height // 2
        want = getattr(TerrainType, near.upper(), TerrainType.GRASS)
        best = None
        for y in range(1, wmap.height - 1):
            for x in range(1, wmap.width - 1):
                if wmap.terrain[y][x] in _BAD or (x, y) in wmap.characters \
                        or (x, y) in used \
                        or self.engine.world.get_location_at(x, y):
                    continue
                if abs(x - px) + abs(y - py) < MIN_DIST:
                    continue
                if any(abs(x - ax) + abs(y - ay) < 6 for ax, ay in used):
                    continue
                on_want = wmap.terrain[y][x] == want or any(
                    0 <= x + dx < wmap.width and 0 <= y + dy < wmap.height
                    and wmap.terrain[y + dy][x + dx] == want
                    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))
                if on_want:
                    return (x, y)
                if best is None:
                    best = (x, y)
        return best

    def _plant_area(self, spec: dict, spot: Tuple[int, int]) -> None:
        from world.location import Location
        cx, cy = spot
        loc = Location(spec["name"], spec.get("legend", ""), cx, cy, 1, 1)
        loc.add_property("adventure", "sunken_tome")
        loc.add_property(spec.get("kind", "site"), spec["id"])
        # The Drowned Vault is entered via its STRUCTURE interior (attached by
        # name, like the Ruined Keep), NOT the procedural CAVE dungeon — so the
        # tile stays open ground and TAB on the marker descends the authored
        # three levels.
        self.engine.world.add_location(loc)
        self.areas.append({"id": spec["id"], "name": spec["name"],
                           "pos": [cx, cy]})

    def _seat_npcs(self, npcs: Dict[str, dict]) -> None:
        for npc_id, spec in npcs.items():
            pos = self._near_area(spec.get("area", ""))
            if pos is None:
                continue
            npc = self._build_npc(npc_id, spec, pos)
            self.engine.npc_manager.add_npc(npc)
            try:
                self.engine.world.map.place_character(npc, *pos)
            except Exception:
                pass
            self.npc_ids.append(npc_id)

    def _near_area(self, area_id: str) -> Optional[Tuple[int, int]]:
        area = next((a for a in self.areas if a["id"] == area_id), None)
        if area is None:
            return None
        wmap = self.engine.world.map
        ax, ay = area["pos"]
        for r in range(1, 5):
            for dy in range(-r, r + 1):
                for dx in range(-r, r + 1):
                    x, y = ax + dx, ay + dy
                    if 0 <= x < wmap.width and 0 <= y < wmap.height \
                            and wmap.terrain[y][x] not in _BAD \
                            and (x, y) not in wmap.characters \
                            and wmap.terrain[y][x] != TerrainType.CAVE:
                        return (x, y)
        return None

    def _build_npc(self, npc_id: str, spec: dict, pos: Tuple[int, int]):
        from characters.character import Character
        from characters.character_types import CharacterClass, CharacterRace
        st = spec.get("stats", {})
        hp = spec.get("hp", 20)
        npc = Character(
            id=npc_id, name=spec["name"],
            character_class=CharacterClass(spec.get("class", "villager")),
            race=CharacterRace(spec.get("race", "human")),
            level=spec.get("level", 1),
            strength=st.get("strength", 10), dexterity=st.get("dexterity", 10),
            constitution=st.get("constitution", 10),
            intelligence=st.get("intelligence", 10),
            wisdom=st.get("wisdom", 10), charisma=st.get("charisma", 10),
            hp=hp, max_hp=hp, position=tuple(pos),
            inventory=list(spec.get("inventory", [])),
            gold=spec.get("gold", 0), symbol=spec.get("symbol", "N"),
            description=spec.get("description", ""),
            personality=dict(spec.get("personality", {})),
            goals=list(spec.get("goals", [])))
        npc.faction = spec.get("faction", "neutral")
        for k, v in spec.get("metadata", {}).items():
            npc.metadata[k] = v
        return npc

    # ---- queries & persistence -------------------------------------

    def is_active(self) -> bool:
        return bool(self.areas)

    def area_pos(self, area_id: str) -> Optional[Tuple[int, int]]:
        a = next((a for a in self.areas if a["id"] == area_id), None)
        return tuple(a["pos"]) if a else None

    def to_dict(self) -> dict:
        return {"seeded": self._seeded, "areas": self.areas,
                "npc_ids": self.npc_ids}

    def from_dict(self, d: dict) -> None:
        d = d or {}
        self._seeded = d.get("seeded", bool(d.get("areas")))
        self.areas = d.get("areas", []) or []
        self.npc_ids = d.get("npc_ids", []) or []
