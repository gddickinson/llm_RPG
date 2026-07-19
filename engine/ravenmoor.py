"""RAVENMOOR — "The Hollowing of Ravenmoor" adventure seeder (George: rich,
complex, multi-objective adventures). A moorland village is being hollowed
out — its people fall into a deathless sleep and rise as thralls — after a
grave-robber woke an ancient barrow-wight. Like the Sunken Tome (P38), the
adventure's AREAS and custom CAST seed here (module packs ship monsters/items/
quests but not NPCs); the 3-act quest chain lives in `data/quests.json`.

`seed()`: plants a `Location` for each area from `data/ravenmoor.json` (near
moorland grass, far from spawn), attaches the `temple_crypt` structure to the
Sunken Barrow as an enterable dungeon, seats the cast (Elder Maeve the
quest-giver, Sister Alenn the wandering cleric), drops Corvin's Journal at his
cottage (the Act-2 FETCH clue), guards the barrow with the risen dead, and
posts a starting rumor. Gated with the adventurers; state persists.
"""

import logging
import os
from typing import Dict, List, Optional, Tuple

from world.world_map import TerrainType

logger = logging.getLogger("llm_rpg.ravenmoor")

_BAD = (TerrainType.BUILDING, TerrainType.WATER, TerrainType.MOUNTAIN)
MIN_DIST = 16


def adventure_npc_ids() -> set:
    """Ids of the NPCs Ravenmoor seeds — kept OUT of data/npcs/ so the general
    roster never carries them, yet quest-giver validators know they exist."""
    from items.data_loader import load_data_file
    try:
        return set((load_data_file("ravenmoor.json") or {}).get("npcs", {}))
    except Exception:
        return set()


class Ravenmoor:
    def __init__(self, engine, seed: int = None):
        self.engine = engine
        self.areas: List[dict] = []
        self.npc_ids: List[str] = []
        self._seeded = False

    def _data(self) -> dict:
        from items.data_loader import load_data_file
        try:
            return load_data_file("ravenmoor.json") or {}
        except Exception as e:
            logger.debug(f"ravenmoor.json: {e}")
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
            spot = self._spot(spec.get("near", "grass"), used)
            if spot is None:
                continue
            used.add(spot)
            self._plant_area(spec, spot)
        self._seat_npcs(data.get("npcs", {}))
        self._place_clue()
        self._place_foes()
        self._rumor()
        if self.areas:
            logger.info(f"Seeded Ravenmoor: {len(self.areas)} areas, "
                        f"{len(self.npc_ids)} NPCs.")
        return len(self.areas)

    def _place_clue(self) -> None:
        """Drop Corvin's Journal at his cottage — the Act-2 FETCH clue that
        names the barrow and the grave-crown Corvin stole."""
        from items.item_registry import create_item
        gi = getattr(self.engine.world, "ground_items", None)
        if gi is None:
            return
        spot = self._near_area("corvins_cottage") or \
            self.area_pos("corvins_cottage")
        if spot is None:
            return
        it = create_item("corvins_journal")
        if it is not None:
            gi.setdefault(tuple(spot), []).append(it)

    def _place_foes(self) -> None:
        """The risen dead haunt the sites — a hollow-thrall by the cottage, a
        grave-warden and thralls guarding the barrow (the Act-2/3 KILLs)."""
        from world.monsters import build_monster
        plan = [("corvins_cottage", "hollow_thrall", 1),
                ("sunken_barrow", "hollow_thrall", 2),
                ("sunken_barrow", "grave_warden", 1),
                ("sunken_barrow", "aedelric_wight", 1)]   # the boss awaits
        wmap = self.engine.world.map
        for area_id, template, n in plan:
            if self.area_pos(area_id) is None:
                continue
            for _ in range(n):
                spot = self._near_area(area_id)
                if spot is None or spot in wmap.characters:
                    continue
                foe = build_monster(template, tuple(spot))
                self.engine.npc_manager.add_npc(foe)
                try:
                    wmap.place_character(foe, *spot)
                except Exception:
                    pass

    def _rumor(self) -> None:
        if not self.areas:
            return
        try:
            self.engine.memory_manager.add_event(
                "[Realm] Travellers shun the moor road past Ravenmoor — its "
                "folk fall to a deathless sleep, and Elder Maeve begs any "
                "brave soul to end the hollowing.")
        except Exception:
            pass

    # ---- placement helpers (mirroring adventure_tome) --------------

    def _spot(self, near: str, used: set) -> Optional[Tuple[int, int]]:
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
        loc.add_property("adventure", "ravenmoor")
        loc.add_property(spec.get("kind", "site"), spec["id"])
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
