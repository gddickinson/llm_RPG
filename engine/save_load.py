"""Save/load system — JSON full-state persistence.

Save format is a single JSON document containing:
- meta: version, timestamp
- world: time, locations, ground items, terrain
- player: full character state
- npcs: list of full NPC states
- quests: quest manager state
- history: memory manager state
"""

import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

import config

logger = logging.getLogger("llm_rpg.save_load")

SAVE_VERSION = 3  # v3: +metadata, equipment, weather, foraging, companions


class SaveManager:
    """Serialize / deserialize game state to JSON."""

    def __init__(self, save_dir: str = None):
        self.save_dir = save_dir or config.SAVE_DIRECTORY
        os.makedirs(self.save_dir, exist_ok=True)

    # ------------------------------------------------------------------ paths

    def save_path(self, name: str) -> str:
        if not name.endswith(".json"):
            name = name + ".json"
        return os.path.join(self.save_dir, name)

    def list_saves(self) -> List[Dict[str, Any]]:
        out = []
        try:
            for f in sorted(os.listdir(self.save_dir)):
                if not f.endswith(".json"):
                    continue
                path = os.path.join(self.save_dir, f)
                try:
                    with open(path, "r") as fp:
                        d = json.load(fp)
                    meta = d.get("meta", {})
                    out.append({
                        "filename": f,
                        "timestamp": meta.get("timestamp", 0),
                        "version": meta.get("version", 0),
                        "label": meta.get("label", ""),
                    })
                except Exception as e:
                    logger.warning(f"Skipping unreadable save {f}: {e}")
        except FileNotFoundError:
            pass
        return out

    # ----------------------------------------------------------------- save

    def save(self, engine, name: str = None, label: str = "") -> str:
        name = name or config.DEFAULT_SAVE_FILE
        path = self.save_path(name)
        payload = self._serialize_engine(engine, label=label)
        tmp = path + ".tmp"
        with open(tmp, "w") as fp:
            # sets (e.g. the P15.11 explored mask) → lists, else str
            json.dump(payload, fp, indent=2,
                      default=lambda o: (sorted(list(o))
                                         if isinstance(o, set)
                                         else str(o)))
        os.replace(tmp, path)
        logger.info(f"Saved game to {path}")
        return path

    # ---------------------------------------------------------------- load

    def load(self, engine, name: str = None) -> bool:
        name = name or config.DEFAULT_SAVE_FILE
        path = self.save_path(name)
        if not os.path.exists(path):
            logger.error(f"Save file does not exist: {path}")
            return False
        with open(path, "r") as fp:
            data = json.load(fp)
        try:
            self._deserialize_into_engine(engine, data)
            logger.info(f"Loaded game from {path}")
            return True
        except Exception as e:
            logger.exception(f"Failed to load save: {e}")
            return False

    # ====================================================== serialization

    def _serialize_engine(self, engine, label: str = "") -> Dict[str, Any]:
        world = engine.world
        player = engine.player
        # Terrain — terrain[y][x] = TerrainType
        terrain = [[cell.value for cell in row] for row in world.map.terrain]

        # Ground items — keys must be strings for JSON. Save the OVERWORLD
        # store even when saving inside a zone (its items are parked while
        # world.ground_items points at the current floor — 2026-07-12).
        ground = {}
        overworld_items = getattr(world, "_overworld_ground_items", None)
        if overworld_items is None:
            overworld_items = getattr(world, "ground_items", {})
        for (x, y), items in (overworld_items or {}).items():
            ground[f"{x},{y}"] = [self._serialize_item(it) for it in items]

        # Locations
        locations = [loc.to_dict() for loc in world.locations]

        # NPCs
        npcs = [self._serialize_character(npc)
                for npc in engine.npc_manager.npcs.values()]

        # Quests
        quests = {}
        if hasattr(engine, "quest_manager") and engine.quest_manager:
            quests = engine.quest_manager.to_dict()

        # History
        history = list(engine.memory_manager.game_history)

        return {
            "meta": {
                "version": SAVE_VERSION,
                "timestamp": time.time(),
                "label": label,
            },
            "world": {
                "width": world.map.width,
                "height": world.map.height,
                "time": world.time,
                "terrain": terrain,
                "ground_items": ground,
                "locations": locations,
            },
            "player": self._serialize_character(player),
            "npcs": npcs,
            "quests": quests,
            "history": history,
            "turn_counter": getattr(engine, "turn_counter", 0),
            "weather": self._subsystem_dict(engine, "weather_system"),
            "foraging": self._subsystem_dict(engine, "forage_manager"),
            "companions": self._subsystem_dict(engine, "companion_manager"),
            "gathering": self._subsystem_dict(engine, "gathering_manager"),
            "director": self._subsystem_dict(engine, "world_director"),
            "factions_state": self._subsystem_dict(engine, "faction_ticker"),
            "faction_agendas": self._subsystem_dict(engine, "faction_agendas"),
            "chronicle": self._subsystem_dict(engine, "chronicle"),
            "production": self._subsystem_dict(engine, "production"),
            "resource_nodes": self._subsystem_dict(engine, "resource_nodes"),
            "lairs": self._subsystem_dict(engine, "lairs"),
            "guildhalls": self._subsystem_dict(engine, "guildhalls"),
            "teleport_network": self._subsystem_dict(engine, "teleport_network"),
            "town_gates": self._subsystem_dict(engine, "town_gates"),
            "adventurers": self._subsystem_dict(engine, "adventurers"),
            "monster_tribes": self._subsystem_dict(engine, "monster_tribes"),
            "nemesis": self._subsystem_dict(engine, "nemesis"),
            "retaliation": self._subsystem_dict(engine, "retaliation"),
            "farms": self._subsystem_dict(engine, "farm_manager"),
            "market": self._subsystem_dict(engine, "market"),
            "doors": self._subsystem_dict(engine, "door_manager"),
            "structures": self._subsystem_dict(engine, "structures"),
            "tile_damage": self._subsystem_dict(engine, "tile_damage"),
            "surfaces": self._subsystem_dict(engine, "surfaces_layer"),
            "flood": self._subsystem_dict(engine, "flood_system"),
            "dm_state": self._subsystem_dict(engine, "dm"),
            "world_history": list(getattr(engine, "world_history", [])),
            "shops": self._subsystem_dict(engine, "shop_manager"),
            "quest_boards": self._subsystem_dict(engine,
                                                 "quest_board_manager"),
            "dungeons": {key: dg.to_dict()
                         for key, dg in getattr(engine, "dungeons", {}).items()},
            "place_state": self._serialize_place_state(engine),
        }

    @staticmethod
    def _serialize_place_state(engine) -> Dict[str, Any]:
        """Where the player 'is' beyond raw coordinates."""
        cur_dungeon_key = None
        for key, dg in getattr(engine, "dungeons", {}).items():
            if dg is getattr(engine, "current_dungeon", None):
                cur_dungeon_key = key
                break
        cur_interior_key = None
        for key, inter in getattr(engine, "interiors", {}).items():
            if inter is getattr(engine, "current_interior", None):
                cur_interior_key = key
                break
        return {
            "current_dungeon": cur_dungeon_key,
            "dungeon_return_pos": getattr(engine, "dungeon_return_pos", None),
            "current_interior": cur_interior_key,
            "exterior_return_pos": getattr(engine, "exterior_return_pos", None),
        }

    @staticmethod
    def _subsystem_dict(engine, attr: str) -> Optional[Dict[str, Any]]:
        sub = getattr(engine, attr, None)
        if sub is not None and hasattr(sub, "to_dict"):
            try:
                return sub.to_dict()
            except Exception as e:
                logger.warning(f"Could not serialize {attr}: {e}")
        return None

    def _serialize_item(self, item: Any) -> Any:
        if hasattr(item, "to_dict"):
            return item.to_dict()
        return str(item)

    def _serialize_character(self, char: Any) -> Dict[str, Any]:
        from items.item import Item
        from characters import equipment as eq
        d = char.to_dict()
        # Override inventory to support full Item objects
        inv = []
        for it in char.inventory:
            if isinstance(it, Item):
                inv.append(it.to_dict())
            else:
                inv.append({"id": None, "name": str(it), "item_type": "misc", "value": 0})
        d["inventory"] = inv
        d["memories"] = list(char.memories) if hasattr(char, "memories") else []
        d["status"] = getattr(char, "status", "alive")
        d["equipment"] = eq.to_dict(char)
        d["home_location"] = getattr(char, "home_location", "")
        return d

    # ---------------------------------------------------------------- restore

    def _deserialize_into_engine(self, engine, data: Dict[str, Any]) -> None:
        from world.world_map import TerrainType
        from items.item import Item
        from characters.character import Character
        from characters.character_types import CharacterClass, CharacterRace

        # World
        wd = data["world"]
        engine.world.map.width = wd["width"]
        engine.world.map.height = wd["height"]
        engine.world.map.terrain = [
            [TerrainType(v) for v in row] for row in wd["terrain"]
        ]
        engine.world.time = wd.get("time", 0)

        # Wipe and reload locations
        from world.location import Location
        engine.world.locations = []
        for ld in wd.get("locations", []):
            loc = Location(
                name=ld["name"], description=ld["description"],
                x=ld["position"][0], y=ld["position"][1],
                width=ld["size"][0], height=ld["size"][1],
            )
            loc.properties = ld.get("properties", {})
            loc.npcs = ld.get("npcs", [])
            engine.world.locations.append(loc)

        # Ground items
        engine.world.ground_items = {}
        for key, items in wd.get("ground_items", {}).items():
            x, y = map(int, key.split(","))
            engine.world.ground_items[(x, y)] = [
                Item.from_dict(it) if isinstance(it, dict) and "id" in it else it
                for it in items
            ]

        # Player
        engine.player = _rebuild_character(data["player"])

        # Place player on map
        engine.world.map.characters = {}
        engine.world.map.place_character(engine.player, *engine.player.position)

        # NPCs
        engine.npc_manager.npcs = {}
        for nd in data.get("npcs", []):
            npc = _rebuild_character(nd)
            engine.npc_manager.npcs[npc.id] = npc
            if npc.is_active():
                engine.world.map.place_character(npc, *npc.position)

        # Rebuild the player roster (M.1b) — the active player plus any
        # player-characters that were living in the NPC pool.
        try:
            engine.roster.rehydrate()
        except Exception:
            pass

        # Quests
        if hasattr(engine, "quest_manager") and engine.quest_manager:
            engine.quest_manager.from_dict(data.get("quests", {}))

        # History
        engine.memory_manager.game_history = list(data.get("history", []))
        engine.turn_counter = data.get("turn_counter", 0)

        # Subsystems (absent in pre-v2 saves — skip silently)
        for key, attr in (("weather", "weather_system"),
                          ("foraging", "forage_manager"),
                          ("companions", "companion_manager"),
                          ("gathering", "gathering_manager"),
                          ("director", "world_director"),
                          ("factions_state", "faction_ticker"),
                          ("faction_agendas", "faction_agendas"),
                          ("chronicle", "chronicle"),
                          ("production", "production"),
                          ("resource_nodes", "resource_nodes"),
                          ("lairs", "lairs"),
                          ("guildhalls", "guildhalls"),
                          ("teleport_network", "teleport_network"),
                          ("town_gates", "town_gates"),
                          ("adventurers", "adventurers"),
                          ("monster_tribes", "monster_tribes"),
                          ("nemesis", "nemesis"),
                          ("retaliation", "retaliation"),
                          ("farms", "farm_manager"),
                          ("market", "market"),
                          ("doors", "door_manager"),
                          ("structures", "structures"),
                          ("tile_damage", "tile_damage"),
                          ("surfaces", "surfaces_layer"),
                          ("flood", "flood_system"),
                          ("dm_state", "dm"),
                          ("shops", "shop_manager"),
                          ("quest_boards", "quest_board_manager")):
            sub = getattr(engine, attr, None)
            payload = data.get(key)
            if sub is not None and payload is not None and hasattr(sub, "from_dict"):
                try:
                    sub.from_dict(payload)
                except Exception as e:
                    logger.warning(f"Could not restore {attr}: {e}")

        engine.world_history = list(data.get("world_history", []))

        # Dungeons + player place state (inside a dungeon / interior)
        from world.dungeon import Dungeon
        engine.dungeons = {}
        for key, dd in data.get("dungeons", {}).items():
            try:
                engine.dungeons[key] = Dungeon.from_dict(dd)
            except Exception as e:
                logger.warning(f"Could not restore dungeon {key}: {e}")

        place = data.get("place_state", {}) or {}
        dg_key = place.get("current_dungeon")
        engine.current_dungeon = engine.dungeons.get(dg_key) if dg_key else None
        pos = place.get("dungeon_return_pos")
        engine.dungeon_return_pos = tuple(pos) if pos else None
        in_key = place.get("current_interior")
        engine.current_interior = (
            getattr(engine, "interiors", {}).get(in_key) if in_key else None)
        pos = place.get("exterior_return_pos")
        engine.exterior_return_pos = tuple(pos) if pos else None


def _rebuild_character(d: Dict[str, Any]):
    """Rebuild a Character from a save dict."""
    from characters.character import Character
    from characters.character_types import CharacterClass, CharacterRace
    from items.item import Item

    inventory = []
    for it in d.get("inventory", []):
        if isinstance(it, dict) and "id" in it and "item_type" in it:
            inventory.append(Item.from_dict(it))
        else:
            inventory.append(it)

    char = Character(
        id=d["id"],
        name=d["name"],
        character_class=CharacterClass(d["class"]),
        race=CharacterRace(d["race"]),
        level=d.get("level", 1),
        strength=d["stats"]["strength"],
        dexterity=d["stats"]["dexterity"],
        constitution=d["stats"]["constitution"],
        intelligence=d["stats"]["intelligence"],
        wisdom=d["stats"]["wisdom"],
        charisma=d["stats"]["charisma"],
        hp=d["hp"],
        max_hp=d["max_hp"],
        position=tuple(d.get("position", (0, 0))),
        inventory=inventory,
        gold=d.get("gold", 0),
        symbol=d.get("symbol", "C"),
        description=d.get("description", ""),
        personality=d.get("personality", {}),
        goals=list(d.get("goals", [])),
        relationships=d.get("relationships", {}),
    )
    char.memories = list(d.get("memories", []))
    char.status = d.get("status", "alive")
    char.faction = d.get("faction", "neutral")
    char.metadata = dict(d.get("metadata", {}))
    char.home_location = d.get("home_location", "")
    if d.get("equipment"):
        from characters import equipment as eq
        eq.from_dict(char, d["equipment"])
    return char
