"""A generic, DATA-DRIVEN adventure seeder (George: rich content, many
complex adventures). Module packs ship monsters/items/quests but NOT NPCs or
areas, so — like the Sunken Tome (`adventure_tome`) and Ravenmoor — an
adventure's places + cast seed here at world start. This one is fully driven
by its JSON, so a NEW adventure is just a data file + a 3-line registration:

    {
      "id": "emberfell",
      "rumor": "Villagers speak of a wyrm on the peak…",
      "areas": [{"id","name","kind","near","legend"}],
      "npcs":  {"npc_id": {name,class,race,level,stats,hp,gold,symbol,area,
                           inventory,description,personality,goals,metadata}},
      "clues": [{"area": <area_id>, "item": <item_id>}],   # drop the clue there
      "foes":  [{"area": <area_id>, "template": <monster>, "count": N}]
    }

`AdventureSeeder(engine, "emberfell.json").seed()`. Gated with the adventurers,
state (areas + npc ids) persists. The multi-act quest chain lives in
`data/quests.json`, chained by `prereq_quest`, given by the seeded NPCs.
"""

import logging
import os
from typing import Dict, List, Optional, Tuple

from world.world_map import TerrainType

logger = logging.getLogger("llm_rpg.adventure_seed")

_BAD = (TerrainType.BUILDING, TerrainType.WATER, TerrainType.MOUNTAIN)
MIN_DIST = 16


# the engine attributes that hold a seeded adventure (AdventureSeeder-based or
# a bespoke seeder exposing resolve()/adventure_id())
ADVENTURE_ATTRS = ("emberfell", "blackbanner", "wychwood", "ravenmoor",
                   "adventure_tome")


def resolve_adventure(engine, adventure_id: str, outcome: str = None) -> bool:
    """Find the seeded adventure matching `adventure_id` and RESOLVE it — a
    finale reshapes the world (guardian foes disperse, the threat thins). Any
    subsystem exposing `resolve()` and either `adventure_id()` or a matching
    attribute name qualifies. Called from `quest_manager.turn_in`."""
    for attr in ADVENTURE_ATTRS:
        sub = getattr(engine, attr, None)
        if sub is None or not hasattr(sub, "resolve"):
            continue
        aid = sub.adventure_id() if hasattr(sub, "adventure_id") else attr
        if aid == adventure_id or attr == adventure_id:
            try:
                return bool(sub.resolve(outcome))
            except Exception as e:
                logger.debug(f"resolve {adventure_id}: {e}")
                return False
    return False


def apply_resolution(engine, foe_ids, data) -> bool:
    """Shared finale world-change (used by AdventureSeeder AND the bespoke
    seeders like Ravenmoor): the surviving guardian foes disperse, the theme's
    wilderness encounters thin (via the lair suppression the encounters read),
    and the lasting `[Realm]` beat is posted."""
    for nid in list(foe_ids or []):
        foe = engine.npc_manager.npcs.get(nid)
        if foe is None or not foe.is_active() \
                or foe.metadata.get("adventure_boss"):
            continue
        try:
            engine.world.map.remove_character(foe)
        except Exception:
            pass
        foe.status = "defeated"
    supp = data.get("suppresses")
    lairs = getattr(engine, "lairs", None)
    if supp and lairs is not None and hasattr(lairs, "_apply_suppression"):
        try:
            lairs._apply_suppression(
                {"name": data.get("resolved_name", "the threat"),
                 "suppresses": supp})
        except Exception:
            pass
    beat = data.get("resolved")
    if beat:
        if not beat.lstrip().startswith("["):
            beat = "[Realm] " + beat
        try:
            engine.memory_manager.add_event(beat)
        except Exception:
            pass
    return True


def npc_ids_of(data_file: str) -> set:
    """The NPC ids an adventure data file seeds — kept OUT of data/npcs/ so the
    general roster never carries them, yet quest-giver validators know them."""
    from items.data_loader import load_data_file
    try:
        return set((load_data_file(data_file) or {}).get("npcs", {}))
    except Exception:
        return set()


class AdventureSeeder:
    def __init__(self, engine, data_file: str, seed: int = None):
        self.engine = engine
        self.data_file = data_file
        self.areas: List[dict] = []
        self.npc_ids: List[str] = []
        self.foe_ids: List[str] = []      # the guardian monsters it planted
        self._seeded = False
        self._resolved = False

    def adventure_id(self) -> str:
        return self._data().get("id", "")

    def _data(self) -> dict:
        from items.data_loader import load_data_file
        try:
            return load_data_file(self.data_file) or {}
        except Exception as e:
            logger.debug(f"{self.data_file}: {e}")
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
            self._plant_area(spec, spot, data.get("id", "adventure"))
        self._seat_npcs(data.get("npcs", {}))
        self._place_clues(data.get("clues", []))
        self._place_foes(data.get("foes", []))
        self._rumor(data.get("rumor"))
        if self.areas:
            logger.info(f"Seeded {data.get('id')}: {len(self.areas)} areas, "
                        f"{len(self.npc_ids)} NPCs.")
        return len(self.areas)

    def _place_clues(self, clues: List[dict]) -> None:
        from items.item_registry import create_item
        gi = getattr(self.engine.world, "ground_items", None)
        if gi is None:
            return
        for c in clues:
            spot = self._near_area(c.get("area", "")) or \
                self.area_pos(c.get("area", ""))
            if spot is None:
                continue
            it = create_item(c.get("item", ""))
            if it is not None:
                gi.setdefault(tuple(spot), []).append(it)

    def _place_foes(self, foes: List[dict]) -> None:
        from world.monsters import build_monster
        wmap = self.engine.world.map
        for f in foes:
            area = f.get("area", "")
            if self.area_pos(area) is None:
                continue
            for _ in range(int(f.get("count", 1))):
                spot = self._near_area(area)
                if spot is None or spot in wmap.characters:
                    continue
                foe = build_monster(f.get("template", "goblin"), tuple(spot))
                foe.metadata["adventure"] = self._data().get("id", "")
                foe.metadata["adventure_boss"] = bool(f.get("boss"))
                self.engine.npc_manager.add_npc(foe)
                self.foe_ids.append(foe.id)
                try:
                    wmap.place_character(foe, *spot)
                except Exception:
                    pass

    def _rumor(self, text: Optional[str]) -> None:
        if not (self.areas and text):
            return
        # honour a load-bearing prefix if the data already carries one,
        # else stamp the [Realm] beat the chronicle/topic systems observe
        if not text.lstrip().startswith("["):
            text = "[Realm] " + text
        try:
            self.engine.memory_manager.add_event(text)
        except Exception:
            pass

    # ---- placement helpers -----------------------------------------

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

    def _plant_area(self, spec: dict, spot: Tuple[int, int],
                    adventure_id: str) -> None:
        from world.location import Location
        cx, cy = spot
        loc = Location(spec["name"], spec.get("legend", ""), cx, cy, 1, 1)
        loc.add_property("adventure", adventure_id)
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

    # ---- finale: the world reflects the victory --------------------

    def resolve(self, outcome: str = None) -> bool:
        """The player finished the finale — so the world CHANGES: the surviving
        guardian foes disperse (the area is safe now), the theme's wilderness
        encounters thin (reusing the lair-suppression the encounters already
        read), and the lasting `[Realm]` beat is posted. Idempotent."""
        if self._resolved or not self.areas:
            return False
        self._resolved = True
        return apply_resolution(self.engine, self.foe_ids, self._data())

    # ---- queries & persistence -------------------------------------

    def is_active(self) -> bool:
        return bool(self.areas)

    def is_resolved(self) -> bool:
        return self._resolved

    def area_pos(self, area_id: str) -> Optional[Tuple[int, int]]:
        a = next((a for a in self.areas if a["id"] == area_id), None)
        return tuple(a["pos"]) if a else None

    def to_dict(self) -> dict:
        return {"seeded": self._seeded, "areas": self.areas,
                "npc_ids": self.npc_ids, "foe_ids": self.foe_ids,
                "resolved": self._resolved}

    def from_dict(self, d: dict) -> None:
        d = d or {}
        self._seeded = d.get("seeded", bool(d.get("areas")))
        self.areas = d.get("areas", []) or []
        self.npc_ids = d.get("npc_ids", []) or []
        self.foe_ids = d.get("foe_ids", []) or []
        self._resolved = d.get("resolved", False)
