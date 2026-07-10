"""The Dungeon Master Tool API (P6.1).

Every power a DM driver (Claude Code session, autonomous LLM, or test)
may exercise, as typed commands: the DM PROPOSES, this API validates
against the charter and DISPOSES. No raw state access.

The charter (enforced here, not by prompt):
- never touches the player directly (no command can);
- never deletes or breaks quests, property, or NPCs;
- creations respect caps: monster level <= player level + 2, item value
  <= 500, quest gold <= 100 + 25*level, terrain brush <= 6x6;
- a budget of MUTATION_BUDGET world-changing acts per game-day;
- every act (and every refusal) is written to the DM notebook.

Definitions (new monsters/items) enter the runtime registries and are
persisted per-save; the cross-campaign Legendarium arrives with P6.7.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("llm_rpg.dm")

MUTATION_BUDGET = 12          # world-changing acts per game-day
MAX_BRUSH = 6                 # terrain edit side length
MAX_ITEM_VALUE = 500
MAX_QUEST_GOLD_BASE = 100
NOTEBOOK_CAP = 200

_EDITABLE_TERRAIN = ("grass", "forest", "water", "swamp", "road",
                     "mountain", "cave")


class DMApi:
    def __init__(self, engine):
        self.engine = engine
        self.notebook: List[dict] = []
        self.scheduled: List[dict] = []          # {day, command, args}
        self.defined_monsters: Dict[str, dict] = {}
        self.defined_items: Dict[str, dict] = {}
        self.campaign_notes: str = ""            # the DM's arc memory
        self._spent: Dict[int, int] = {}         # day -> mutations used

    # ---- bookkeeping ----------------------------------------------------

    def _day(self) -> int:
        return self.engine.world.time // (24 * 60)

    def _log(self, command: str, ok: bool, note: str) -> Tuple[bool, str]:
        self.notebook.append({"day": self._day(), "command": command,
                              "ok": ok, "note": note})
        del self.notebook[:-NOTEBOOK_CAP]
        (logger.info if ok else logger.debug)(f"DM {command}: {note}")
        return (ok, note)

    def _charge(self, command: str) -> Optional[Tuple[bool, str]]:
        day = self._day()
        if self._spent.get(day, 0) >= MUTATION_BUDGET:
            return self._log(command, False,
                             f"budget exhausted ({MUTATION_BUDGET}/day)")
        self._spent[day] = self._spent.get(day, 0) + 1
        return None

    def budget_remaining(self) -> int:
        return MUTATION_BUDGET - self._spent.get(self._day(), 0)

    def _protected_region(self, x: int, y: int, w: int, h: int) -> str:
        """Charter: never overwrite standing structures — refuse any
        region touching BUILDING terrain or a typed POI location."""
        from world.world_map import TerrainType
        wmap = self.engine.world.map
        for yy in range(y, min(y + h, wmap.height)):
            for xx in range(x, min(x + w, wmap.width)):
                if wmap.terrain[yy][xx] == TerrainType.BUILDING:
                    return "overlaps an existing structure (charter)"
        for loc in self.engine.world.locations:
            if not (loc.properties or {}).get("type"):
                continue
            if x < loc.x + loc.width and loc.x < x + w and \
                    y < loc.y + loc.height and loc.y < y + h:
                return f"overlaps {loc.name} (charter)"
        return ""

    def digest(self) -> dict:
        """The DM's view of the table (P6.2)."""
        from engine.dm_digest import build_digest
        return build_digest(self.engine)

    def install_module(self, module: dict) -> Tuple[bool, str]:
        """Atomic adventure bundle (P6.5)."""
        from engine.dm_modules import install_module
        return install_module(self.engine, module)

    # ---- narration (free) --------------------------------------------------

    def narrate(self, text: str) -> Tuple[bool, str]:
        text = str(text).strip()[:300]
        if not text:
            return self._log("narrate", False, "empty")
        self.engine.memory_manager.add_event(f"[DM] {text}")
        return self._log("narrate", True, text[:80])

    # ---- definitions ----------------------------------------------------------

    def define_monster(self, template_id: str,
                       spec: dict) -> Tuple[bool, str]:
        from world.monsters import MONSTER_TEMPLATES
        from characters.character_types import CharacterClass, CharacterRace
        if template_id in MONSTER_TEMPLATES:
            return self._log("define_monster", False,
                             f"'{template_id}' already exists")
        cap = self.engine.player.level + 2
        if spec.get("level", 1) > cap:
            return self._log("define_monster", False,
                             f"level cap is {cap}")
        try:
            CharacterClass(spec.get("class", "monster"))
            CharacterRace(spec.get("race", "goblin"))
        except ValueError as e:
            return self._log("define_monster", False, str(e))
        if not spec.get("name"):
            return self._log("define_monster", False, "needs a name")
        denied = self._charge("define_monster")
        if denied:
            return denied
        MONSTER_TEMPLATES[template_id] = dict(spec)
        self.defined_monsters[template_id] = dict(spec)
        return self._log("define_monster", True,
                         f"{template_id}: {spec['name']}")

    def define_item(self, item_id: str, spec: dict) -> Tuple[bool, str]:
        from items.item_registry import ITEM_REGISTRY
        from items.item import Item
        if item_id in ITEM_REGISTRY:
            return self._log("define_item", False,
                             f"'{item_id}' already exists")
        if spec.get("value", 1) > MAX_ITEM_VALUE:
            return self._log("define_item", False,
                             f"value cap is {MAX_ITEM_VALUE}")
        entry = dict(spec)
        entry.setdefault("id", item_id)
        try:
            item = Item.from_dict(entry)
        except (KeyError, ValueError) as e:
            return self._log("define_item", False, f"bad spec: {e}")
        denied = self._charge("define_item")
        if denied:
            return denied
        ITEM_REGISTRY[item_id] = item
        self.defined_items[item_id] = entry
        return self._log("define_item", True, f"{item_id}: {item.name}")

    # ---- world placement ---------------------------------------------------------

    def spawn_npc(self, template_id: str,
                  position: Tuple[int, int]) -> Tuple[bool, str]:
        from world.monsters import MONSTER_TEMPLATES, build_monster
        if template_id not in MONSTER_TEMPLATES:
            return self._log("spawn_npc", False,
                             f"unknown template '{template_id}'")
        x, y = position
        wmap = self.engine.world.map
        if not (0 <= x < wmap.width and 0 <= y < wmap.height):
            return self._log("spawn_npc", False, "out of bounds")
        px, py = self.engine.player.position
        if abs(x - px) + abs(y - py) < 6:
            return self._log("spawn_npc", False,
                             "too close to the player (charter)")
        denied = self._charge("spawn_npc")
        if denied:
            return denied
        npc = build_monster(template_id, (x, y))
        self.engine.npc_manager.add_npc(npc)
        wmap.place_character(npc, x, y)
        return self._log("spawn_npc", True,
                         f"{npc.name} at {position}")

    def place_item(self, item_id: str,
                   position: Tuple[int, int]) -> Tuple[bool, str]:
        from items.item_registry import create_item
        item = create_item(item_id)
        if item is None:
            return self._log("place_item", False,
                             f"unknown item '{item_id}'")
        x, y = position
        wmap = self.engine.world.map
        if not (0 <= x < wmap.width and 0 <= y < wmap.height):
            return self._log("place_item", False, "out of bounds")
        denied = self._charge("place_item")
        if denied:
            return denied
        self.engine.world.add_item_to_ground(item, x, y)
        return self._log("place_item", True, f"{item.name} at {position}")

    def add_building(self, name: str, x: int, y: int, w: int, h: int,
                     description: str = "",
                     properties: dict = None) -> Tuple[bool, str]:
        from world.world_map import TerrainType
        from world.location import Location
        if not name:
            return self._log("add_building", False, "needs a name")
        if any(loc.name == name for loc in self.engine.world.locations):
            return self._log("add_building", False,
                             f"'{name}' already exists")
        if w < 1 or h < 1 or w > MAX_BRUSH or h > MAX_BRUSH:
            return self._log("add_building", False,
                             f"size cap is {MAX_BRUSH}x{MAX_BRUSH}")
        wmap = self.engine.world.map
        if not (0 <= x and 0 <= y and x + w <= wmap.width and
                y + h <= wmap.height):
            return self._log("add_building", False, "out of bounds")
        px, py = self.engine.player.position
        if x <= px < x + w and y <= py < y + h:
            return self._log("add_building", False,
                             "would bury the player (charter)")
        protected = self._protected_region(x, y, w, h)
        if protected:
            return self._log("add_building", False, protected)
        denied = self._charge("add_building")
        if denied:
            return denied
        for yy in range(y, y + h):
            for xx in range(x, x + w):
                wmap.terrain[yy][xx] = TerrainType.BUILDING
        loc = Location(name, description or "A new structure.",
                       x, y, w, h)
        loc.properties = dict(properties or {})
        self.engine.world.add_location(loc)
        return self._log("add_building", True, f"{name} at ({x},{y})")

    def edit_terrain(self, x: int, y: int, w: int, h: int,
                     terrain: str) -> Tuple[bool, str]:
        from world.world_map import TerrainType
        if terrain not in _EDITABLE_TERRAIN:
            return self._log("edit_terrain", False,
                             f"terrain '{terrain}' not editable")
        if w < 1 or h < 1 or w > MAX_BRUSH or h > MAX_BRUSH:
            return self._log("edit_terrain", False,
                             f"brush cap is {MAX_BRUSH}x{MAX_BRUSH}")
        wmap = self.engine.world.map
        if not (0 <= x and 0 <= y and x + w <= wmap.width and
                y + h <= wmap.height):
            return self._log("edit_terrain", False, "out of bounds")
        px, py = self.engine.player.position
        if x <= px < x + w and y <= py < y + h and \
                terrain in ("water", "mountain"):
            return self._log("edit_terrain", False,
                             "would trap the player (charter)")
        protected = self._protected_region(x, y, w, h)
        if protected:
            return self._log("edit_terrain", False, protected)
        denied = self._charge("edit_terrain")
        if denied:
            return denied
        tt = TerrainType(terrain)
        for yy in range(y, y + h):
            for xx in range(x, x + w):
                wmap.terrain[yy][xx] = tt
        return self._log("edit_terrain", True,
                         f"{terrain} {w}x{h} at ({x},{y})")

    # ---- story ---------------------------------------------------------------

    def create_quest(self, quest_id: str, spec: dict) -> Tuple[bool, str]:
        qm = self.engine.quest_manager
        if qm is None:
            return self._log("create_quest", False, "quests disabled")
        if quest_id in qm.quests:
            return self._log("create_quest", False,
                             f"'{quest_id}' already exists")
        gold_cap = MAX_QUEST_GOLD_BASE + 25 * self.engine.player.level
        if spec.get("reward_gold", 0) > gold_cap:
            return self._log("create_quest", False,
                             f"reward cap is {gold_cap}g")
        giver = spec.get("giver_id", "")
        if giver and self.engine.npc_manager.get_npc(giver) is None:
            return self._log("create_quest", False,
                             f"unknown giver '{giver}'")
        try:
            from quests.quest_templates import _quest_from_entry
            quest = _quest_from_entry(quest_id, spec)
        except (KeyError, ValueError) as e:
            return self._log("create_quest", False, f"bad spec: {e}")
        denied = self._charge("create_quest")
        if denied:
            return denied
        from quests.quest import QuestStatus
        quest.status = QuestStatus.AVAILABLE
        qm.quests[quest_id] = quest
        try:
            self.engine.radiant_quests._post(quest_id)
        except Exception:
            pass
        return self._log("create_quest", True,
                         f"{quest_id}: {quest.title}")

    def adjust_faction(self, faction: str, delta: int) -> Tuple[bool, str]:
        delta = max(-10, min(10, int(delta)))
        try:
            from characters.factions import modify_rep, Faction
            fac = Faction(faction)
        except ValueError:
            return self._log("adjust_faction", False,
                             f"unknown faction '{faction}'")
        denied = self._charge("adjust_faction")
        if denied:
            return denied
        modify_rep(self.engine.player, fac, delta)
        return self._log("adjust_faction", True, f"{faction} {delta:+d}")

    def schedule_beat(self, day: int, command: str,
                      args: dict = None) -> Tuple[bool, str]:
        if day <= self._day():
            return self._log("schedule_beat", False,
                             "must schedule a FUTURE day")
        if not hasattr(self, command) or command.startswith("_") or \
                command in ("schedule_beat", "run_scheduled"):
            return self._log("schedule_beat", False,
                             f"unknown command '{command}'")
        self.scheduled.append({"day": day, "command": command,
                               "args": dict(args or {})})
        return self._log("schedule_beat", True,
                         f"{command} on day {day}")

    def run_scheduled(self) -> int:
        """Execute beats due today (called on day change)."""
        today = self._day()
        due = [b for b in self.scheduled if b["day"] <= today]
        self.scheduled = [b for b in self.scheduled if b["day"] > today]
        for beat in due:
            try:
                getattr(self, beat["command"])(**beat["args"])
            except Exception as e:
                self._log(beat["command"], False, f"beat failed: {e}")
        return len(due)

    # ---- persistence -----------------------------------------------------------

    def to_dict(self):
        return {"notebook": self.notebook[-NOTEBOOK_CAP:],
                "scheduled": list(self.scheduled),
                "defined_monsters": dict(self.defined_monsters),
                "defined_items": dict(self.defined_items),
                "campaign_notes": self.campaign_notes,
                "spent": {str(k): v for k, v in self._spent.items()}}

    def from_dict(self, d):
        self.notebook = list(d.get("notebook", []))
        self.scheduled = list(d.get("scheduled", []))
        self.defined_monsters = dict(d.get("defined_monsters", {}))
        self.defined_items = dict(d.get("defined_items", {}))
        self.campaign_notes = str(d.get("campaign_notes", ""))
        self._spent = {int(k): v
                       for k, v in d.get("spent", {}).items()}
        # Re-inject definitions into the runtime registries
        from world.monsters import MONSTER_TEMPLATES
        from items.item_registry import ITEM_REGISTRY
        from items.item import Item
        for tid, spec in self.defined_monsters.items():
            MONSTER_TEMPLATES.setdefault(tid, dict(spec))
        for iid, spec in self.defined_items.items():
            if iid not in ITEM_REGISTRY:
                try:
                    ITEM_REGISTRY[iid] = Item.from_dict(dict(spec))
                except Exception:
                    pass
