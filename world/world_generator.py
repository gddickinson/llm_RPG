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
        self.seed = seed
        self.rng = random.Random(seed)
        self.w = world.map.width
        self.h = world.map.height
        self.elevation = None

    # ----- public -----------------------------------------------------

    def generate(self) -> None:
        self._fill_base()
        self._add_forest_borders()
        self._add_river()
        self._add_road()
        self._add_mountain_range()
        self._add_village()
        if self.w >= 50 and self.h >= 30:
            self._add_second_settlement()
            self._add_connecting_road()
        if self.w >= 100 and self.h >= 60:
            self._add_third_settlement()
            self._add_third_road()
            self._add_secondary_river()
        self._add_cave()
        if self.w >= 100:
            self._add_second_cave()
        if self.w >= 100 and self.h >= 60:
            self._add_extra_civic_buildings()
            self._add_wilderness_buildings()
            self._add_murkfen_swamp()
        self._add_wilderness_features()
        self._fortify_start_town()
        logger.info(f"Procedural world generated ({self.w}x{self.h}) "
                    f"with {len(self.world.locations)} locations")

    def _fortify_start_town(self) -> None:
        """P31.1 — ring Oakvale with a curtain wall, gates where the roads
        cross, so the start town is defensible and monster-free (guards are
        posted at the gates in demo_setup, where the NPC manager lives)."""
        from world.fortify import fortify
        oak = next((l for l in self.world.locations
                    if l.name == "Oakvale Village"), None)
        if oak is None:
            return
        gates = fortify(self.world.map, oak, margin=2)
        oak.add_property("gates", [list(g) for g in gates])

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
        # An elevation-driven river: water follows the valley floor
        # downhill across the map (P16.6), seed-reproducible.
        from world.river_gen import elevation_field, trace_river
        self.elevation = elevation_field(self.w, self.h, self.seed)
        for x, y in trace_river(self.elevation, self.w, self.h):
            self.world.map.terrain[y][x] = TerrainType.WATER

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

    def _add_murkfen_swamp(self) -> None:
        """The Murkfen — a brooding swamp in the south-central lowlands."""
        sx, sy = self.w // 2 - 8, self.h - 18
        sw, sh = 22, 13
        for y in range(sy, min(self.h - 1, sy + sh)):
            for x in range(sx, min(self.w - 1, sx + sw)):
                current = self.world.map.terrain[y][x]
                if current in (TerrainType.BUILDING, TerrainType.ROAD,
                               TerrainType.CAVE):
                    continue
                roll = self.rng.random()
                if roll < 0.72:
                    self.world.map.terrain[y][x] = TerrainType.SWAMP
                elif roll < 0.82:
                    self.world.map.terrain[y][x] = TerrainType.WATER
        self.world.add_location(Location(
            "The Murkfen",
            "A brooding swamp of black pools and whispering reeds.",
            sx, sy, sw, sh,
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
        loc = Location(name, desc, x, y, x2 - x, y2 - y)
        # Auto-tag locations by name keywords
        low = name.lower()
        if "forge" in low or "smith" in low:
            loc.add_property("type", "forge")
            loc.add_property("forge", True)
        elif "tavern" in low:
            loc.add_property("type", "tavern")
        elif "temple" in low or "shrine" in low:
            loc.add_property("type", "temple")
        elif "shop" in low or "store" in low:
            loc.add_property("type", "shop")
        self.world.add_location(loc)

    def _add_second_settlement(self) -> None:
        """Riverside Hamlet — a second town in the south-west."""
        vx = max(4, self.w // 8)
        vy = min(self.h - 8, self.h // 2 + 8)
        vw, vh = 9, 5
        self.world.add_location(Location(
            "Riverside Hamlet",
            "A quiet hamlet by the river. Smoke curls from the chimneys.",
            vx, vy, vw, vh,
        ))
        self._building(vx + 1, vy + 1, 2, 2,
                       "Riverside Inn",
                       "A small inn for road-weary travelers.")
        self._building(vx + 5, vy + 1, 2, 2,
                       "Wheelwright's Shop",
                       "A shop full of axles and yokes.")
        self._building(vx + 1, vy + 3, 2, 2,
                       "Hamlet Chapel",
                       "A modest chapel of the Light.")

    def _add_connecting_road(self) -> None:
        """Lay a road between Oakvale and Riverside Hamlet."""
        # Find center of each by location bounds
        oakvale = next((l for l in self.world.locations
                        if l.name == "Oakvale Village"), None)
        riverside = next((l for l in self.world.locations
                          if l.name == "Riverside Hamlet"), None)
        if not (oakvale and riverside):
            return
        ax, ay = oakvale.center()
        bx, by = riverside.center()
        # L-shape path: horizontal then vertical
        for x in range(min(ax, bx), max(ax, bx) + 1):
            if 0 <= x < self.w and 0 <= ay < self.h:
                t = self.world.map.terrain[ay][x]
                if t == TerrainType.WATER:
                    self.world.map.terrain[ay][x] = TerrainType.BRIDGE
                elif t != TerrainType.BUILDING:
                    self.world.map.terrain[ay][x] = TerrainType.ROAD
        for y in range(min(ay, by), max(ay, by) + 1):
            if 0 <= y < self.h and 0 <= bx < self.w:
                t = self.world.map.terrain[y][bx]
                if t == TerrainType.WATER:
                    self.world.map.terrain[y][bx] = TerrainType.BRIDGE
                elif t != TerrainType.BUILDING:
                    self.world.map.terrain[y][bx] = TerrainType.ROAD

    def _add_third_settlement(self) -> None:
        """Stonepine Camp — a mining/lumber outpost near the mountains."""
        # Place it on the eastern edge near the mountain range, but lower
        # than the mountains themselves
        vx = max(self.w - 16, self.w // 2 + 5)
        vy = min(self.h - 10, int(self.h * 0.65))
        vw, vh = 8, 5
        self.world.add_location(Location(
            "Stonepine Camp",
            "A weathered logging and mining outpost at the mountain's foot.",
            vx, vy, vw, vh,
        ))
        self._building(vx + 1, vy + 1, 2, 2,
                       "Foreman's Hall",
                       "A long log hall where the foreman keeps the ledgers.")
        self._building(vx + 5, vy + 1, 2, 2,
                       "Stonepine Smithy",
                       "A small forge for repairing picks and saws.")
        self._building(vx + 1, vy + 3, 2, 2,
                       "Camp Tavern",
                       "Rough-hewn benches, a barrel of strong ale.")

    def _add_third_road(self) -> None:
        """Connect Stonepine to the existing road network."""
        oakvale = next((l for l in self.world.locations
                        if l.name == "Oakvale Village"), None)
        stonepine = next((l for l in self.world.locations
                          if l.name == "Stonepine Camp"), None)
        if not (oakvale and stonepine):
            return
        ax, ay = oakvale.center()
        bx, by = stonepine.center()
        # Vertical first, then horizontal
        for y in range(min(ay, by), max(ay, by) + 1):
            if 0 <= y < self.h and 0 <= ax < self.w:
                t = self.world.map.terrain[y][ax]
                if t == TerrainType.WATER:
                    self.world.map.terrain[y][ax] = TerrainType.BRIDGE
                elif t not in (TerrainType.BUILDING,
                               TerrainType.MOUNTAIN):
                    self.world.map.terrain[y][ax] = TerrainType.ROAD
        for x in range(min(ax, bx), max(ax, bx) + 1):
            if 0 <= x < self.w and 0 <= by < self.h:
                t = self.world.map.terrain[by][x]
                if t == TerrainType.WATER:
                    self.world.map.terrain[by][x] = TerrainType.BRIDGE
                elif t not in (TerrainType.BUILDING,
                               TerrainType.MOUNTAIN):
                    self.world.map.terrain[by][x] = TerrainType.ROAD

    def _add_secondary_river(self) -> None:
        """A vertical tributary feeding the main river."""
        # Pick a column in the right half, snake from the main river
        # upward to the top edge
        x = self.rng.randint(self.w * 3 // 5, self.w - 5)
        # Find the river's y in this column
        for y in range(self.h):
            if self.world.map.terrain[y][x] == TerrainType.WATER:
                start_y = y
                break
        else:
            start_y = self.h // 2
        # Snake upward
        for y in range(start_y, 0, -1):
            if 0 <= x < self.w:
                if self.world.map.terrain[y][x] not in (
                        TerrainType.BUILDING, TerrainType.MOUNTAIN,
                        TerrainType.ROAD):
                    self.world.map.terrain[y][x] = TerrainType.WATER
            # Drift
            if self.rng.random() < 0.4 and 1 <= x < self.w - 1:
                x += self.rng.choice([-1, 0, 0, 1])

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

    def _add_second_cave(self) -> None:
        """A second cave entrance, distinct from the first."""
        # Look for a mountain tile not adjacent to the first cave
        attempts = 50
        while attempts > 0:
            attempts -= 1
            cx = self.rng.randint(self.w * 3 // 4, self.w - 2)
            cy = self.rng.randint(0, max(2, self.h // 3 - 1))
            if not (0 <= cx < self.w and 0 <= cy < self.h):
                continue
            terrain = self.world.map.terrain[cy][cx]
            if terrain != TerrainType.MOUNTAIN:
                continue
            # Don't overwrite the existing Dark Cave or stack on top of it
            existing = self.world.get_location_at(cx, cy)
            if existing and existing.name == "Dark Cave":
                continue
            if abs(cx - (self.w - 3)) <= 2 and abs(cy - 3) <= 2:
                continue
            self.world.map.terrain[cy][cx] = TerrainType.CAVE
            self.world.add_location(Location(
                "Goblin Warrens",
                "A foul-smelling cave entrance, rumored to house goblins.",
                cx, cy, 1, 1,
            ))
            return

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
        from world.world_map import TerrainType
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
