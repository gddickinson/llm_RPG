"""Destructible tiles (P10.2, slimmed from AW's durability.py).

The world takes damage: tiles have materials and hit points, tracked
sparsely (only wounded tiles cost memory). Stone resists fire but
crumbles to siege; wood burns fast. Destruction flips terrain through
WorldMap.set_terrain — firing the P10.0 callbacks — and leaves what
you'd expect: walls become RUBBLE, burnt groves become SCORCHED
earth, felled ones plain grass.

A breached building wall (RUBBLE on the footprint) becomes a SECOND
DOOR: bump the gap and you clamber inside, no lock consulted — smash
your way in and the trespass system (P9A.4) still judges you.

AoE spells damage tiles in their radius (fireball uses the fire
multiplier — one cast fells a tree, twenty crack a stone wall).
Sparse HP persists via save_load.
"""

import logging
from typing import Dict, Optional, Tuple

from world.world_map import TerrainType

logger = logging.getLogger("llm_rpg.tile_damage")

MATERIALS = {
    "stone": {"physical": 1.0, "fire": 0.3, "siege": 1.5},
    "wood": {"physical": 1.0, "fire": 2.0, "siege": 1.5},
    "light": {"physical": 1.5, "fire": 2.0, "siege": 2.0},
}
TILE_MATERIAL = {
    TerrainType.BUILDING: "stone",
    TerrainType.FOREST: "wood",
    TerrainType.FARMLAND: "light",
    TerrainType.MOUNTAIN: "stone",
    TerrainType.BRIDGE: "wood",
}
TILE_BASE_HP = {
    TerrainType.BUILDING: 60,
    TerrainType.FOREST: 20,
    TerrainType.FARMLAND: 10,
    TerrainType.MOUNTAIN: 80,
    TerrainType.BRIDGE: 30,
}
TILE_DESTROYED = {
    TerrainType.BUILDING: TerrainType.RUBBLE,
    TerrainType.FOREST: TerrainType.GRASS,
    TerrainType.FARMLAND: TerrainType.SCORCHED,
    TerrainType.MOUNTAIN: TerrainType.GRASS,
    TerrainType.BRIDGE: TerrainType.WATER,
}
DESTROY_LINES = {
    TerrainType.BUILDING: "Masonry gives way — the wall collapses "
                          "into rubble!",
    TerrainType.FOREST: "The tree splinters and falls!",
    TerrainType.FARMLAND: "The field is torn apart.",
    TerrainType.MOUNTAIN: "The rock gives way — you've cut a "
                          "tunnel through!",
    TerrainType.BRIDGE: "The bridge groans, splinters — and drops "
                        "into the water!",
}


RUBBLE_BLOCK_DEPTH = 2       # piled this high, you must clear it


class TileDamage:
    def __init__(self, engine):
        self.engine = engine
        self.tile_hp: Dict[Tuple[int, int], int] = {}
        # rubble depth per tile: 1 = clamberable breach, 2+ = blocked
        self.rubble_depth: Dict[Tuple[int, int], int] = {}

    def damage_tile(self, x: int, y: int, amount: int,
                    attack_type: str = "physical") -> Optional[str]:
        """Damage one overworld tile. Returns a message on
        destruction (or a first-crack warning), else None."""
        wmap = self.engine.world.map
        if not (0 <= x < wmap.width and 0 <= y < wmap.height):
            return None
        terrain = wmap.terrain[y][x]
        material = TILE_MATERIAL.get(terrain)
        if material is None:
            return None
        mult = MATERIALS[material].get(attack_type, 1.0)
        dmg = int(amount * mult)
        if dmg <= 0:
            return None
        base = TILE_BASE_HP[terrain]
        hp = self.tile_hp.get((x, y), base)
        cracked_before = hp <= base // 2
        hp -= dmg
        if hp <= 0:
            self.tile_hp.pop((x, y), None)
            destroyed = TILE_DESTROYED[terrain]
            if attack_type == "fire" and terrain in (
                    TerrainType.FOREST, TerrainType.FARMLAND):
                destroyed = TerrainType.SCORCHED
            wmap.set_terrain(x, y, destroyed)
            if destroyed == TerrainType.RUBBLE:
                self.rubble_depth[(x, y)] = \
                    self.rubble_depth.get((x, y), 0) + 1
            msg = DESTROY_LINES.get(terrain, "It breaks apart.")
            self.engine.memory_manager.add_event(msg)
            return msg
        self.tile_hp[(x, y)] = hp
        if terrain == TerrainType.BUILDING and not cracked_before \
                and hp <= base // 2:
            msg = "Cracks spider across the stonework."
            self.engine.memory_manager.add_event(msg)
            return msg
        return None

    def damage_radius(self, cx: int, cy: int, amount: int,
                      radius: float,
                      attack_type: str = "physical") -> int:
        """Damage every destructible tile in the blast. Returns how
        many were destroyed."""
        destroyed = 0
        r = int(radius) + 1
        for y in range(cy - r, cy + r + 1):
            for x in range(cx - r, cx + r + 1):
                if ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5 > radius:
                    continue
                msg = self.damage_tile(x, y, amount, attack_type)
                if msg and "rubble" in msg or \
                        (msg and ("falls" in msg or "torn" in msg)):
                    destroyed += 1
        return destroyed

    # ------------------------------------------------------- rubble

    def depth_at(self, x: int, y: int) -> int:
        return self.rubble_depth.get((x, y), 0)

    def add_rubble(self, x: int, y: int, depth: int = 1) -> None:
        """Debris arrives (collapses, giants, clearing dumps)."""
        wmap = self.engine.world.map
        if not (0 <= x < wmap.width and 0 <= y < wmap.height):
            return
        self.rubble_depth[(x, y)] = \
            self.rubble_depth.get((x, y), 0) + depth
        if wmap.terrain[y][x] not in (TerrainType.WATER,
                                      TerrainType.MOUNTAIN,
                                      TerrainType.RUBBLE):
            wmap.set_terrain(x, y, TerrainType.RUBBLE)

    def clear_rubble(self, x: int, y: int) -> Optional[str]:
        """Shift one layer of debris to the least-buried adjacent
        tile — moved, never deleted (George: giants and workers MOVE
        debris)."""
        depth = self.rubble_depth.get((x, y), 0)
        if depth <= 0:
            return None
        wmap = self.engine.world.map
        best, best_depth = None, 10 ** 6
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if not (0 <= nx < wmap.width and 0 <= ny < wmap.height):
                continue
            if wmap.terrain[ny][nx] in (TerrainType.WATER,
                                        TerrainType.MOUNTAIN,
                                        TerrainType.BUILDING):
                continue
            d = self.rubble_depth.get((nx, ny), 0)
            if d < best_depth:
                best, best_depth = (nx, ny), d
        if best is None:
            return "There is nowhere to shift the debris."
        self.rubble_depth[(x, y)] = depth - 1
        self.add_rubble(best[0], best[1], 1)
        if self.rubble_depth[(x, y)] <= 0:
            self.rubble_depth.pop((x, y), None)
            wmap.set_terrain(x, y, TerrainType.GRASS)
            msg = "You heave the last of the stone aside — clear!"
        else:
            msg = (f"You shift broken stone aside "
                   f"({self.rubble_depth[(x, y)]} layers left).")
        self.engine.memory_manager.add_event(msg)
        return msg

    # ---------------------------------------------------- persistence

    def to_dict(self) -> dict:
        return {"hp": [[x, y, hp] for (x, y), hp in
                       self.tile_hp.items()],
                "rubble": [[x, y, d] for (x, y), d in
                           self.rubble_depth.items()]}

    def from_dict(self, data: dict) -> None:
        self.tile_hp = {(int(x), int(y)): int(hp)
                        for x, y, hp in data.get("hp", [])}
        self.rubble_depth = {(int(x), int(y)): int(d)
                             for x, y, d in data.get("rubble", [])}
