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
    # Multi-level (P9.5): same stack convention as interiors
    depth: int = 1
    stairs_down: "Tuple[int, int]" = None
    stairs_up: "Tuple[int, int]" = None
    level_below: "Dungeon" = None
    level_above: "Dungeon" = None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "width": self.width,
            "height": self.height,
            "terrain": [[c.value for c in row] for row in self.terrain],
            "rooms": [[r.x, r.y, r.w, r.h] for r in self.rooms],
            "exit_pos": list(self.exit_pos),
            "spawned": self.spawned,
            "description": self.description,
            "depth": self.depth,
            "stairs_down": list(self.stairs_down)
            if self.stairs_down else None,
            "stairs_up": list(self.stairs_up)
            if self.stairs_up else None,
            "below": self.level_below.to_dict()
            if self.level_below else None,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Dungeon":
        out = cls(
            name=d["name"],
            width=d["width"],
            height=d["height"],
            terrain=[[TerrainType(v) for v in row] for row in d["terrain"]],
            rooms=[DungeonRoom(*r) for r in d.get("rooms", [])],
            exit_pos=tuple(d.get("exit_pos", (1, 1))),
            spawned=d.get("spawned", False),
            description=d.get("description", ""),
        )
        out.depth = d.get("depth", 1)
        if d.get("stairs_down"):
            out.stairs_down = tuple(d["stairs_down"])
        if d.get("stairs_up"):
            out.stairs_up = tuple(d["stairs_up"])
        if d.get("below"):
            below = cls.from_dict(d["below"])
            out.level_below = below
            below.level_above = out
        return out


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


def generate_multilevel(name: str, seed: int = None,
                        engine=None, depth: int = None) -> Dungeon:
    """P9.5: a 2-3 level dungeon. Deeper floors hold stronger
    monsters; the deepest holds a boss and its hoard. Stairs use the
    same linked convention as building levels.

    GX.5: `depth` forces an exact number of levels (a DEEP delve like the
    Oakvale Deepdelve runs 5-6 floors); omitted, it rolls the classic 2-3."""
    rng = random.Random(seed)
    depth_levels = max(1, depth) if depth else rng.randint(2, 3)
    levels = []
    for i in range(depth_levels):
        lv = generate_dungeon(
            name=f"{name} — depth {i + 1}" if i else name,
            seed=(seed or 0) + i * 7919,
            description="Damp, echoing tunnels." if i == 0 else
            ("The air is colder here." if i < depth_levels - 1 else
             "Something large has made this floor its den."))
        lv.depth = i + 1
        levels.append(lv)
    for upper, lower in zip(levels, levels[1:]):
        down_room = upper.rooms[-1]
        upper.stairs_down = down_room.center()
        lower.stairs_up = lower.rooms[0].center()
        upper.level_below = lower
        lower.level_above = upper
    if engine is not None:
        for lv in levels:
            populate_dungeon(lv, engine, rng=rng)
    return levels[0]


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
    from world.monsters import build_monster, dungeon_pool
    from characters.character import Character

    depth = getattr(d, "depth", 1)
    is_boss_floor = depth > 1 and getattr(d, "level_below", None) is None

    # Drop a few items + a monster in each non-entrance room
    for room in d.rooms[1:]:
        cx, cy = room.center()
        # Loot (richer as you go down)
        for item_id in rng.sample(
                ["potion", "coins", "bandage", "old_map", "rusty_key",
                 "herb_bundle"], k=min(2 + depth - 1, 4)):
            item = create_item(item_id)
            if item:
                engine.world.add_item_to_ground(item, cx, cy)
        # Monster, scaled to the depth (P9.5); T1.3 depth-gates the POOL so a
        # tough foe only appears deep (not on a first-floor low-level hero)
        template = rng.choice(dungeon_pool(depth) or dungeon_pool())
        monster = build_monster(template, (cx, cy))
        if depth > 1:
            monster.level += depth - 1
            monster.max_hp += 4 * (depth - 1)
            monster.hp = monster.max_hp
        monster.metadata["zone"] = d.name
        engine.npc_manager.add_npc(monster)
        engine.world.map.place_character(monster, cx, cy)

    # The deepest floor has a den-lord and its hoard — drawn from the
    # apex pool for this depth (P19.1): the built bosses become reachable
    # and a dragon may wait in the deep dark.
    if is_boss_floor and d.rooms:
        from world.monsters import apex_pool
        bx, by = d.rooms[-1].center()
        pool = apex_pool(depth) or ["tyrant_depths"]
        template = rng.choice(pool)
        boss = build_monster(template, (bx, by))
        boss.level += depth
        boss.max_hp += 10 * depth
        boss.hp = boss.max_hp
        boss.metadata["zone"] = d.name
        engine.npc_manager.add_npc(boss)
        engine.world.map.place_character(boss, bx, by)
        for item_id in ("greater_potion", "greater_potion",
                        "scroll_heal"):
            item = create_item(item_id)
            if item:
                engine.world.add_item_to_ground(item, bx + 1, by)
    d.spawned = True
