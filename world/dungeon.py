"""Procedural dungeon generation.

A `Dungeon` has its own terrain grid, ground items, monsters, and an
exit tile. Entering a cave tile loads a fresh dungeon (or restores it
from save state).

Generator: simple BSP-lite — start with all-wall, carve out rooms,
connect with corridors.
"""

import logging
import random
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from world.world_map import TerrainType

logger = logging.getLogger("llm_rpg.dungeon")


@dataclass
class DungeonRoom:
    x: int
    y: int
    w: int
    h: int

    def center(self) -> Tuple[int, int]:
        return (self.x + self.w // 2, self.y + self.h // 2)

    def intersects(self, other: "DungeonRoom") -> bool:
        return not (self.x + self.w + 1 < other.x or
                    other.x + other.w + 1 < self.x or
                    self.y + self.h + 1 < other.y or
                    other.y + other.h + 1 < self.y)


@dataclass
class Dungeon:
    """A small grid-based dungeon level."""
    name: str
    width: int
    height: int
    terrain: List[List[TerrainType]] = field(default_factory=list)
    rooms: List[DungeonRoom] = field(default_factory=list)
    exit_pos: Tuple[int, int] = (1, 1)
    spawned: bool = False                  # whether monsters/items placed
    description: str = ""


def generate_dungeon(name: str = "Cave Tunnels",
                     width: int = 24, height: int = 16,
                     seed: int = None,
                     description: str = "Damp, echoing tunnels.") -> Dungeon:
    rng = random.Random(seed)
    d = Dungeon(name=name, width=width, height=height,
                description=description)
    # Start with all walls
    d.terrain = [[TerrainType.MOUNTAIN for _ in range(width)]
                 for _ in range(height)]

    # Carve rooms
    max_rooms = 6
    min_room, max_room = 3, 6
    for _ in range(max_rooms * 2):
        w = rng.randint(min_room, max_room)
        h = rng.randint(min_room, max_room)
        x = rng.randint(1, width - w - 2)
        y = rng.randint(1, height - h - 2)
        room = DungeonRoom(x, y, w, h)
        if any(room.intersects(r) for r in d.rooms):
            continue
        d.rooms.append(room)
        _carve_room(d, room)
        if len(d.rooms) >= max_rooms:
            break

    if not d.rooms:
        # Fallback: ensure at least one room exists
        room = DungeonRoom(2, 2, 5, 4)
        d.rooms.append(room)
        _carve_room(d, room)

    # Connect rooms with corridors
    for i in range(1, len(d.rooms)):
        c1 = d.rooms[i - 1].center()
        c2 = d.rooms[i].center()
        _carve_corridor(d, c1, c2, rng)

    # Exit (back to overworld) on first room
    d.exit_pos = d.rooms[0].center()
    d.terrain[d.exit_pos[1]][d.exit_pos[0]] = TerrainType.ROAD

    return d


def _carve_room(d: Dungeon, room: DungeonRoom) -> None:
    for y in range(room.y, room.y + room.h):
        for x in range(room.x, room.x + room.w):
            if 0 <= x < d.width and 0 <= y < d.height:
                d.terrain[y][x] = TerrainType.GRASS


def _carve_corridor(d: Dungeon, a: Tuple[int, int],
                    b: Tuple[int, int], rng: random.Random) -> None:
    x1, y1 = a
    x2, y2 = b
    # Random order: horizontal-first or vertical-first
    if rng.random() < 0.5:
        for x in range(min(x1, x2), max(x1, x2) + 1):
            d.terrain[y1][x] = TerrainType.GRASS
        for y in range(min(y1, y2), max(y1, y2) + 1):
            d.terrain[y][x2] = TerrainType.GRASS
    else:
        for y in range(min(y1, y2), max(y1, y2) + 1):
            d.terrain[y][x1] = TerrainType.GRASS
        for x in range(min(x1, x2), max(x1, x2) + 1):
            d.terrain[y2][x] = TerrainType.GRASS


def populate_dungeon(d: Dungeon, engine, rng: random.Random = None) -> None:
    """Spawn monsters + loot in rooms (except the entrance)."""
    rng = rng or random.Random()
    if d.spawned or len(d.rooms) <= 1:
        d.spawned = True
        return

    from items.item_registry import create_item
    from world.encounters import _build_monster
    from characters.character import Character

    # Drop a few items + a monster in each non-entrance room
    for room in d.rooms[1:]:
        cx, cy = room.center()
        # Loot
        for item_id in rng.sample(
                ["potion", "coins", "bandage", "old_map", "rusty_key",
                 "herb_bundle"], k=2):
            item = create_item(item_id)
            if item:
                engine.world.add_item_to_ground(item, cx, cy)
        # Monster
        template = rng.choice(["goblin", "wolf", "bandit"])
        monster = _build_monster(template, (cx, cy))
        engine.npc_manager.add_npc(monster)
        engine.world.map.place_character(monster, cx, cy)
    d.spawned = True
