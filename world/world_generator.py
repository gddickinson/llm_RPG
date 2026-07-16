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
from world.worldgen_extras import WorldGenExtrasMixin

logger = logging.getLogger("llm_rpg.worldgen")


class WorldGenerator(WorldGenExtrasMixin):
    """Procedurally fills a World with terrain + named locations."""

    def __init__(self, world, seed: int = 42, mode: str = "classic"):
        self.world = world
        self.seed = seed
        self.mode = mode                       # "classic" | "realistic" (P36.1)
        self.rng = random.Random(seed)
        self.w = world.map.width
        self.h = world.map.height
        self.elevation = None

    # ----- public -----------------------------------------------------

    def generate(self) -> None:
        if self.mode == "realistic":
            return self._generate_realistic()
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

    def _generate_realistic(self) -> None:
        """P36.1 a heightmap LANDSCAPE (mountains, forests, lakes, coasts, marsh)
        instead of flat grass; the settlements clear playable land within it."""
        from world import realistic_gen
        self.elevation = realistic_gen.assign_terrain(self.world.map, self.seed)
        realistic_gen.carve_rivers(self.world.map, self.elevation)   # P36.2
        self._add_village()
        if self.w >= 50 and self.h >= 30:
            self._add_second_settlement()
            self._add_connecting_road()
        if self.w >= 100 and self.h >= 60:
            self._add_third_settlement()
            self._add_third_road()
        self._carve_town_clearings()           # towns clear the land they sit on
        self._clear_start_town_interior()      # ...esp. the whole WALLED enclosure
        self._fortify_start_town()
        self._add_cave()
        if self.w >= 100:
            self._add_second_cave()
        if self.w >= 100 and self.h >= 60:
            self._add_extra_civic_buildings()
            self._add_wilderness_buildings()
        self._add_wilderness_features()
        self._place_history()                  # P36.3 ruins + the age's chronicle
        logger.info(f"Realistic world generated ({self.w}x{self.h}) with "
                    f"{len(self.world.locations)} locations")

    def _place_history(self) -> None:
        """P36.3 run the deep-history sim, scatter its RUINS across the land and
        stash the CHRONICLE on the world for the Y-journal."""
        from world import world_history
        terrain_copy = [row[:] for row in self.world.map.terrain]
        hist = world_history.simulate(terrain_copy, self.seed)
        occupied = {(l.x, l.y) for l in self.world.locations}
        for r in hist["ruins"]:
            if any(abs(r.x - ox) + abs(r.y - oy) <= 4 for ox, oy in occupied):
                continue                        # don't drop a ruin onto a town
            self._place_ruin(r)
        self.world.history_chronicle = hist["chronicle"]

    def _place_ruin(self, r) -> None:
        from world.location import Location
        land = (TerrainType.GRASS, TerrainType.FOREST)
        for dy in range(-1, 2):
            for dx in range(-1, 2):
                x, y = r.x + dx, r.y + dy
                if 0 <= x < self.w and 0 <= y < self.h and \
                        self.world.map.terrain[y][x] in land:
                    self.world.map.terrain[y][x] = TerrainType.RUBBLE
        if self.rng.random() < 0.5:             # some ruins hide a dungeon
            self.world.map.terrain[r.y][r.x] = TerrainType.CAVE
        loc = Location(f"{r.name} Ruins",
                       f"Ruins — {r.legend}. Fallen in year {r.year}.",
                       max(0, r.x - 1), max(0, r.y - 1), 3, 3)
        loc.add_property("ruin", r.kind)
        loc.add_property("legend", r.legend)
        self.world.add_location(loc)

    def _clear_start_town_interior(self) -> None:
        """Bug-fix (George): a realistic world walls Oakvale, but heightmap water /
        mountains INSIDE the wall trapped the hero with no reachable gate. Clear the
        whole fortified enclosure to walkable ground BEFORE the wall goes up, so the
        courtyard is passable and the gate is reachable (roads/bridges/caves kept)."""
        oak = next((l for l in self.world.locations
                    if l.name == "Oakvale Village"), None)
        if oak is None:
            return
        from world.fortify import town_members, extent
        try:
            x0, y0, x1, y1 = extent(town_members(self.world, oak, radius=12),
                                    margin=3)
        except Exception:
            x0, y0 = oak.x - 6, oak.y - 6
            x1, y1 = oak.x + oak.width + 6, oak.y + oak.height + 6
        keep = (TerrainType.BUILDING, TerrainType.ROAD, TerrainType.BRIDGE,
                TerrainType.CAVE)
        wild = (TerrainType.WATER, TerrainType.MOUNTAIN, TerrainType.SWAMP)
        for y in range(max(0, y0), min(self.h, y1 + 1)):
            for x in range(max(0, x0), min(self.w, x1 + 1)):
                t = self.world.map.terrain[y][x]
                if t in wild and t not in keep:
                    self.world.map.terrain[y][x] = TerrainType.GRASS

    def _carve_town_clearings(self) -> None:
        """Flatten the untamed terrain (water / mountain / marsh) inside a
        settlement's footprint + a margin to walkable grass, so a town founded on
        the heightmap sits in a proper clearing (roads / bridges / walls kept)."""
        keep = (TerrainType.BUILDING, TerrainType.ROAD, TerrainType.BRIDGE,
                TerrainType.CAVE)
        wild = (TerrainType.WATER, TerrainType.MOUNTAIN, TerrainType.SWAMP)
        for loc in list(self.world.locations):
            if not any(k in loc.name.lower()
                       for k in ("village", "hamlet", "town", "outpost")):
                continue
            m = 3
            for y in range(max(0, loc.y - m),
                           min(self.h, loc.y + loc.height + m)):
                for x in range(max(0, loc.x - m),
                               min(self.w, loc.x + loc.width + m)):
                    t = self.world.map.terrain[y][x]
                    if t in wild and t not in keep:
                        self.world.map.terrain[y][x] = TerrainType.GRASS

    def _fortify_start_town(self) -> None:
        """P31.1/P31.1b — ring the WHOLE Oakvale town (village + its nearby
        buildings: the library, forge, market…) with a curtain wall, gates
        where the roads cross, and a GUARD TOWER at each corner. Guards for the
        gates and towers are posted in demo_setup (where the NPC manager lives)."""
        from world.fortify import fortify_town
        oak = next((l for l in self.world.locations
                    if l.name == "Oakvale Village"), None)
        if oak is None:
            return
        res = fortify_town(self.world, oak, margin=2, radius=12)
        oak.add_property("gates", [list(g) for g in res["gates"]])
        oak.add_property("towers", [list(c) for c in res["corners"]])

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
        # GX.4: a LARGE church below the village core (a 6x5 footprint opens into
        # a ~26x22 nave — room to seat scores, George's ask), on clear ground
        # with its south door facing open grass.
        cx, cy = vx + 1, min(self.h - 6, vy + vh + 2)
        for yy in range(cy, min(cy + 6, self.h)):
            for xx in range(cx, min(cx + 6, self.w)):
                if self.world.map.terrain[yy][xx] != TerrainType.BUILDING:
                    self.world.map.terrain[yy][xx] = TerrainType.GRASS
        self._building(cx, cy, 6, 5,
                       "Oakvale Cathedral",
                       "A great stone cathedral, its bell tolling over the vale.")

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
        elif "cathedral" in low or "church" in low:
            loc.add_property("type", "cathedral")
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

    # ----- extra civic + wilderness placement -------------------------
    #   _add_extra_civic_buildings / _add_wilderness_buildings /
    #   _add_wilderness_features / _blob live in world/worldgen_extras.py
    #   (WorldGenExtrasMixin) to hold the 500-line line (GX.4).
