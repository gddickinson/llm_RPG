"""Extra civic + wilderness placement for `WorldGenerator` (split to hold the
500-line line — GX.4).

`WorldGenExtrasMixin` carries the placement passes that dress the world AFTER
the settlements + roads are laid: the extra Oakvale civic buildings (watchtower
/ well / market stall / library), the scattered wilderness buildings
(farmhouses / lodge / shrine / wizard's tower), the forest + mountain-spur
feature blobs, and the `_blob` terrain-stamp helper they share. `WorldGenerator`
inherits it, so every method runs as a normal bound method over the generator's
own `self.world`/`self.rng`/`self.w`/`self.h`/`self._building`.
"""

import logging

from world.world_map import TerrainType

logger = logging.getLogger("llm_rpg.worldgen")


class WorldGenExtrasMixin:
    """Civic + wilderness placement passes mixed into `WorldGenerator`."""

    def _add_extra_civic_buildings(self) -> None:
        """Add a watchtower, well, market stall, library in/around Oakvale."""
        oakvale = next((l for l in self.world.locations
                        if l.name == "Oakvale Village"), None)
        if not oakvale:
            return
        cx, cy = oakvale.center()
        # Watchtower north of the village
        self._building(cx - 3, cy - 8, 2, 2,
                       "Oakvale Watchtower",
                       "A wooden tower watching the road.")
        # Well in the middle of the village
        self._building(cx + 4, cy - 1, 1, 1,
                       "Village Well",
                       "A round stone well — the village's water.")
        # Market stall on the road
        self._building(cx - 4, cy - 1, 2, 1,
                       "Oakvale Market Stall",
                       "A canvas market stall with fresh produce.")
        # Library
        self._building(cx + 6, cy - 3, 2, 2,
                       "Oakvale Library",
                       "A modest library of leather-bound tomes.")

    def _add_wilderness_buildings(self) -> None:
        """Sprinkle farmhouses, hunter's lodge, wayside shrine, wizard tower."""
        attempts = 0
        wanted = [
            ("Old Farmhouse", "A weathered farmhouse, fields gone fallow.", 2, 2),
            ("Abandoned Cottage", "A tumbledown cottage, its roof half-caved and door hanging.", 2, 2),
            ("Roadside Farm", "A small farm beside the road.", 2, 2),
            ("Hunter's Lodge", "A log lodge with antlers above the door.", 2, 2),
            ("Wayside Shrine", "A lichen-covered roadside shrine.", 1, 1),
            ("Stable", "Wooden stables; the smell of hay.", 2, 2),
            ("Wizard's Tower", "A slim stone tower, capped with a glowing roof.", 2, 2),
            ("Abandoned Watchtower", "An old timber watchtower, half-fallen.", 1, 2),
        ]
        placed = 0
        while wanted and attempts < 200:
            attempts += 1
            name, desc, bw, bh = wanted[0]
            x = self.rng.randint(4, self.w - bw - 4)
            y = self.rng.randint(4, self.h - bh - 4)
            # Stay on grass and away from other locations
            ok = True
            for dy in range(bh):
                for dx in range(bw):
                    if not (0 <= x + dx < self.w and 0 <= y + dy < self.h):
                        ok = False
                        break
                    if self.world.map.terrain[y + dy][x + dx] != \
                            TerrainType.GRASS:
                        ok = False
                        break
                if not ok:
                    break
            if not ok:
                continue
            if any(loc.contains(x, y) for loc in self.world.locations):
                continue
            # Distance check: not too close to a village center
            too_close = False
            for loc in self.world.locations:
                ltype = loc.get_property("type", "")
                if ltype not in ("tavern", "forge", "temple", "shop", "hall"):
                    continue
                lx, ly = loc.center()
                if (lx - x) ** 2 + (ly - y) ** 2 < 30:
                    too_close = True
                    break
            if too_close:
                continue
            self._building(x, y, bw, bh, name, desc)
            wanted.pop(0)
            placed += 1
        logger.info(f"Placed {placed} wilderness buildings.")

    def _add_wilderness_features(self) -> None:
        # Forest blobs — density scales with map area
        area_factor = (self.w * self.h) // 600   # ~4 at 60x40, ~16 at 120x80
        for _ in range(area_factor * 2):
            cx = self.rng.randint(2, self.w - 3)
            cy = self.rng.randint(2, self.h - 3)
            if self.world.map.terrain[cy][cx] == TerrainType.GRASS:
                radius = self.rng.randint(2, 3)
                self._blob(cx, cy, radius, TerrainType.FOREST)

        # Mountain spurs (small clusters off the main range)
        for _ in range(max(1, area_factor // 2)):
            cx = self.rng.randint(self.w // 2, self.w - 4)
            cy = self.rng.randint(2, self.h - 4)
            if self.world.map.terrain[cy][cx] == TerrainType.GRASS:
                self._blob(cx, cy, 2, TerrainType.MOUNTAIN)

    def _blob(self, cx: int, cy: int, radius: int,
              terrain: TerrainType) -> None:
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
