"""Chunked-world streaming.

When the player walks off the edge of the current map, the engine
generates an adjacent region from a world-plan seed and stitches it in.

The world plan is a coarse-grained grid of (region_x, region_y) -> seed.
Each region is generated procedurally by WorldGenerator. The current
WorldMap holds the data for a single region at a time, but
ChunkedWorld remembers visited regions so the player can backtrack.
"""

import logging
import random
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

logger = logging.getLogger("llm_rpg.chunked_world")


@dataclass
class RegionPlan:
    """Coarse-grained plan for one region: seed + region type."""
    seed: int
    flavor: str = "wilderness"   # village / wilderness / mountain / forest / coast


@dataclass
class ChunkedWorld:
    """Sparse store of all regions we know about."""
    world_seed: int = 42
    region_size: Tuple[int, int] = (120, 80)
    regions: Dict[Tuple[int, int], RegionPlan] = field(default_factory=dict)
    cached_terrain: Dict[Tuple[int, int], list] = field(default_factory=dict)
    cached_locations: Dict[Tuple[int, int], list] = field(default_factory=dict)
    current_region: Tuple[int, int] = (0, 0)

    def plan_for(self, rx: int, ry: int) -> RegionPlan:
        if (rx, ry) in self.regions:
            return self.regions[(rx, ry)]
        # Deterministic per-region seed
        rng = random.Random(self.world_seed + rx * 1000003 + ry * 1009)
        # Region flavor by Manhattan distance from origin
        d = abs(rx) + abs(ry)
        if (rx, ry) == (0, 0):
            flavor = "home"   # the starter region — full village
        elif d == 1:
            flavor = "wilderness"
        elif rx >= 1 and abs(ry) <= 1:
            flavor = rng.choice(["forest", "wilderness"])
        elif ry <= -1:
            flavor = rng.choice(["mountain", "wilderness"])
        elif ry >= 2:
            flavor = rng.choice(["coast", "forest"])
        else:
            flavor = rng.choice(["wilderness", "forest", "mountain"])
        plan = RegionPlan(seed=rng.randint(1, 10**6), flavor=flavor)
        self.regions[(rx, ry)] = plan
        return plan


class WorldStreamer:
    """Bridges ChunkedWorld with the live engine.

    On `transit_player(direction)` it:
    1. Saves the current region's terrain to cache.
    2. Loads (or generates) the neighboring region.
    3. Repositions the player at the opposite edge of the new region.
    """

    def __init__(self, engine, world_seed: int = 42):
        self.engine = engine
        self.cw = ChunkedWorld(world_seed=world_seed)

    # ------------------------------------------------------------------

    def at_world_edge(self) -> Optional[str]:
        """Return the edge the player is standing on, or None."""
        if self.engine.current_interior or self.engine.current_dungeon:
            return None
        x, y = self.engine.player.position
        w, h = self.engine.world.map.width, self.engine.world.map.height
        if x <= 0:
            return "west"
        if x >= w - 1:
            return "east"
        if y <= 0:
            return "north"
        if y >= h - 1:
            return "south"
        return None

    def transit(self, direction: str) -> Optional[str]:
        """Move the player into the adjacent region. Returns event string."""
        if self.engine.current_interior or self.engine.current_dungeon:
            return None
        rx, ry = self.cw.current_region
        dx, dy = {
            "north": (0, -1), "south": (0, 1),
            "east": (1, 0), "west": (-1, 0),
        }.get(direction, (0, 0))
        new_rx, new_ry = rx + dx, ry + dy

        # Cache current region
        self._cache_current()

        # Generate / restore new region
        if (new_rx, new_ry) in self.cw.cached_terrain:
            self._restore(new_rx, new_ry)
        else:
            self._generate(new_rx, new_ry)

        # Drop player at the opposite edge
        w, h = self.engine.world.map.width, self.engine.world.map.height
        old_x, old_y = self.engine.player.position
        if direction == "east":
            new_x, new_y = 1, max(1, min(h - 2, old_y))
        elif direction == "west":
            new_x, new_y = w - 2, max(1, min(h - 2, old_y))
        elif direction == "south":
            new_x, new_y = max(1, min(w - 2, old_x)), 1
        else:
            new_x, new_y = max(1, min(w - 2, old_x)), h - 2
        self.engine.world.map.remove_character(self.engine.player)
        self.engine.player.position = (new_x, new_y)
        self.engine.world.map.place_character(self.engine.player, new_x, new_y)
        self.cw.current_region = (new_rx, new_ry)
        plan = self.cw.plan_for(new_rx, new_ry)
        msg = (f"You travel {direction} into a new region "
               f"({plan.flavor}, [{new_rx},{new_ry}]).")
        self.engine.memory_manager.add_event(msg)
        return msg

    # ------------------------------------------------------------------

    def _cache_current(self) -> None:
        rx, ry = self.cw.current_region
        wmap = self.engine.world.map
        self.cw.cached_terrain[(rx, ry)] = [list(row) for row in wmap.terrain]
        self.cw.cached_locations[(rx, ry)] = list(self.engine.world.locations)

    def _restore(self, rx: int, ry: int) -> None:
        terrain = self.cw.cached_terrain[(rx, ry)]
        locations = self.cw.cached_locations[(rx, ry)]
        self.engine.world.map.terrain = [list(row) for row in terrain]
        self.engine.world.locations = list(locations)
        # Clear non-player characters from the map; NPC manager untouched
        self._reset_map_characters()
        self._rebuild_interiors()

    def _generate(self, rx: int, ry: int) -> None:
        plan = self.cw.plan_for(rx, ry)
        from world.world_generator import WorldGenerator
        # Wipe world state
        self.engine.world.locations = []
        gen = WorldGenerator(self.engine.world, seed=plan.seed)
        # Light-touch fill based on flavor
        if plan.flavor == "wilderness":
            gen._fill_base()
            gen._add_forest_borders()
            gen._add_wilderness_features()
        elif plan.flavor == "forest":
            gen._fill_base()
            from world.world_map import TerrainType
            for y in range(self.engine.world.map.height):
                for x in range(self.engine.world.map.width):
                    if gen.rng.random() < 0.45:
                        self.engine.world.map.terrain[y][x] = \
                            TerrainType.FOREST
            gen._add_wilderness_features()
        elif plan.flavor == "mountain":
            gen._fill_base()
            from world.world_map import TerrainType
            for y in range(self.engine.world.map.height):
                for x in range(self.engine.world.map.width):
                    if gen.rng.random() < 0.4:
                        self.engine.world.map.terrain[y][x] = \
                            TerrainType.MOUNTAIN
            gen._add_wilderness_features()
        elif plan.flavor == "coast":
            gen._fill_base()
            from world.world_map import TerrainType
            for y in range(self.engine.world.map.height):
                for x in range(self.engine.world.map.width):
                    if x > self.engine.world.map.width * 0.6:
                        self.engine.world.map.terrain[y][x] = \
                            TerrainType.WATER
            gen._add_wilderness_features()
        else:
            gen.generate()
        self._reset_map_characters()
        self._rebuild_interiors()

    def _reset_map_characters(self) -> None:
        wmap = self.engine.world.map
        wmap.characters = {}

    def _rebuild_interiors(self) -> None:
        try:
            from world.interiors import build_interiors_for_world
            self.engine.interiors = build_interiors_for_world(self.engine.world)
        except Exception:
            pass
