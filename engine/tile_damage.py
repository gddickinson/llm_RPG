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
}
TILE_BASE_HP = {
    TerrainType.BUILDING: 60,
    TerrainType.FOREST: 20,
    TerrainType.FARMLAND: 10,
}
TILE_DESTROYED = {
    TerrainType.BUILDING: TerrainType.RUBBLE,
    TerrainType.FOREST: TerrainType.GRASS,
    TerrainType.FARMLAND: TerrainType.SCORCHED,
}
DESTROY_LINES = {
    TerrainType.BUILDING: "Masonry gives way — the wall collapses "
                          "into rubble!",
    TerrainType.FOREST: "The tree splinters and falls!",
    TerrainType.FARMLAND: "The field is torn apart.",
}


class TileDamage:
    def __init__(self, engine):
        self.engine = engine
        self.tile_hp: Dict[Tuple[int, int], int] = {}

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

    # ---------------------------------------------------- persistence

    def to_dict(self) -> dict:
        return {"hp": [[x, y, hp] for (x, y), hp in
                       self.tile_hp.items()]}

    def from_dict(self, data: dict) -> None:
        self.tile_hp = {(int(x), int(y)): int(hp)
                        for x, y, hp in data.get("hp", [])}
