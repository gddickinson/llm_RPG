"""Procedural world generator.

Generates a coherent map with:
- Background biomes (plains/forest)
- Forest borders and mountain ranges
- A river crossing the map
- A road bisecting it
- Oakvale Village with tavern, forge, shop, temple
- Cave + mountain region
- Wilderness shrines

Lightweight — no perlin noise dependency, just simple region-fill with
small randomization. Reproducible via seed.
"""

import logging
import random
from typing import List, Tuple

from world.world_map import TerrainType
from world.location import Location

logger = logging.getLogger("llm_rpg.worldgen")


class WorldGenerator:
    """Procedurally fills a World with terrain + named locations."""

    def __init__(self, world, seed: int = 42):
        self.world = world
        self.rng = random.Random(seed)
        self.w = world.map.width
        self.h = world.map.height

    # ----- public -----------------------------------------------------

    def generate(self) -> None:
        self._fill_base()
        self._add_forest_borders()
        self._add_river()
        self._add_road()
        self._add_mountain_range()
        self._add_village()
        self._add_cave()
        self._add_wilderness_features()
        logger.info(f"Procedural world generated ({self.w}x{self.h})")

    # ----- terrain ----------------------------------------------------

    def _fill_base(self) -> None:
        for y in range(self.h):
            for x in range(self.w):
                self.world.map.terrain[y][x] = TerrainType.GRASS

    def _add_forest_borders(self) -> None:
        # Sparse forest along top and bottom edges
        for y in range(0, 3):
            for x in range(self.w):
                if self.rng.random() < 0.65:
                    self.world.map.terrain[y][x] = TerrainType.FOREST
        for y in range(self.h - 3, self.h):
            for x in range(self.w):
                if self.rng.random() < 0.65:
                    self.world.map.terrain[y][x] = TerrainType.FOREST
        # Forest patches on sides
        for _ in range(self.w // 6):
            cx = self.rng.randint(0, 5)
            cy = self.rng.randint(4, self.h - 5)
            self._blob(cx, cy, 3, TerrainType.FOREST)
        for _ in range(self.w // 6):
            cx = self.rng.randint(self.w - 6, self.w - 1)
            cy = self.rng.randint(4, self.h - 5)
            self._blob(cx, cy, 3, TerrainType.FOREST)

    def _add_river(self) -> None:
        # A meandering horizontal river
        y = self.h // 2
        for x in range(self.w):
            self.world.map.terrain[y][x] = TerrainType.WATER
            if self.rng.random() < 0.3 and 1 <= y < self.h - 1:
                y += self.rng.choice([-1, 0, 0, 1])
                y = max(2, min(self.h - 3, y))

    def _add_road(self) -> None:
        # Road runs along y = h//2 - 3 (above the river)
        ry = max(2, self.h // 2 - 3)
        for x in range(self.w):
            if self.world.map.terrain[ry][x] == TerrainType.WATER:
                continue
            self.world.map.terrain[ry][x] = TerrainType.ROAD

    def _add_mountain_range(self) -> None:
        # Mountains in the NE corner
        for y in range(0, max(3, self.h // 3)):
            for x in range(self.w - max(5, self.w // 4), self.w):
                if self.rng.random() < 0.55:
                    self.world.map.terrain[y][x] = TerrainType.MOUNTAIN
        # Named location for mountains
        mx = self.w - max(5, self.w // 4)
        my = 0
        mw = self.w - mx
        mh = max(3, self.h // 3)
        self.world.add_location(Location(
            "Misty Mountains",
            "Tall mountains shrouded in mist.",
            mx, my, mw, mh,
        ))

    def _add_village(self) -> None:
        # Oakvale Village near the road
        vx = max(8, self.w // 3)
        vy = max(3, self.h // 2 - 5)
        vw, vh = 10, 5
        self.world.add_location(Location(
            "Oakvale Village",
            "A small peaceful village surrounded by forests.",
            vx, vy, vw, vh,
        ))

        # Buildings inside
        self._building(vx + 1, vy + 1, 2, 2,
                       "Oakvale Tavern",
                       "A cozy tavern with a warm hearth.")
        self._building(vx + 5, vy + 1, 2, 2,
                       "Durgan's Forge",
                       "A busy blacksmith shop, sound of hammering.")
        self._building(vx + 1, vy + 3, 2, 2,
                       "General Store",
                       "A shop with various goods and supplies.")
        self._building(vx + 5, vy + 3, 2, 2,
                       "Temple of Light",
                       "A small temple dedicated to the gods of light.")

    def _building(self, x, y, w, h, name, desc) -> None:
        x2 = min(x + w, self.w)
        y2 = min(y + h, self.h)
        for yy in range(y, y2):
            for xx in range(x, x2):
                self.world.map.terrain[yy][xx] = TerrainType.BUILDING
        self.world.add_location(Location(name, desc, x, y, x2 - x, y2 - y))

    def _add_cave(self) -> None:
        # Cave entrance in mountain region
        cx = self.w - 3
        cy = 3
        if cy < self.h and cx < self.w:
            self.world.map.terrain[cy][cx] = TerrainType.CAVE
            self.world.add_location(Location(
                "Dark Cave",
                "A mysterious cave entrance in the mountainside.",
                cx, cy, 1, 1,
            ))

    def _add_wilderness_features(self) -> None:
        # A few scattered forest blobs in wilderness
        for _ in range(self.w // 4):
            cx = self.rng.randint(2, self.w - 3)
            cy = self.rng.randint(2, self.h - 3)
            if self.world.map.terrain[cy][cx] == TerrainType.GRASS:
                self._blob(cx, cy, 2, TerrainType.FOREST)

    # ----- helpers ----------------------------------------------------

    def _blob(self, cx: int, cy: int, radius: int, terrain: TerrainType) -> None:
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                x, y = cx + dx, cy + dy
                if not (0 <= x < self.w and 0 <= y < self.h):
                    continue
                if dx * dx + dy * dy > radius * radius:
                    continue
                # Don't overwrite roads, water, or buildings
                if self.world.map.terrain[y][x] in (
                        TerrainType.ROAD, TerrainType.WATER,
                        TerrainType.BUILDING, TerrainType.CAVE):
                    continue
                if self.rng.random() < 0.7:
                    self.world.map.terrain[y][x] = terrain
