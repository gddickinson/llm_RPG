"""Floods & damming (P10.6) — water is a frontier you can stop.

A flood starts at a source tile (a storm-swollen bank, or a DM's
cruelty) and spreads as a cellular frontier: every few turns the
water claims adjacent low ground — grass, road, farmland, swamp,
scorched earth. It does NOT cross buildings, mountains, forest or
RUBBLE: piled debris is a DAM, which makes the P10.4 rubble economy
a flood defense — giants knock down what would have kept the water
out, and a player heaving stone into a line can save a field.

Floods remember what they drowned. When the water's turns run out
it recedes, restoring the original terrain tile by tile. Occupied
tiles are never flooded (the water laps around the stubborn);
proper swimming arrives with Phase 11.

Storms can start one: while a storm rages there's a small per-turn
chance the nearest water's edge bursts. At most one flood at a time.
"""

import logging
import random

from world.world_map import TerrainType

logger = logging.getLogger("llm_rpg.flood")

FLOODABLE = (TerrainType.GRASS, TerrainType.ROAD,
             TerrainType.FARMLAND, TerrainType.SWAMP,
             TerrainType.SCORCHED)
SPREAD_INTERVAL = 4        # turns between frontier rings
DEFAULT_DURATION = 240     # turns before the water recedes
DEFAULT_MAX_TILES = 40     # a flood, not an ocean
STORM_FLOOD_CHANCE = 0.002  # per turn, during a storm


class FloodSystem:
    def __init__(self, engine):
        self.engine = engine
        self.floods = []       # {frontier, flooded, turns_left, max}
        self.rng = random.Random()

    # ------------------------------------------------------------ api

    def start_flood(self, x: int, y: int,
                    duration: int = DEFAULT_DURATION,
                    max_tiles: int = DEFAULT_MAX_TILES) -> bool:
        wmap = self.engine.world.map
        if not (0 <= x < wmap.width and 0 <= y < wmap.height):
            return False
        flood = {"frontier": [[x, y]], "flooded": [],
                 "turns_left": duration, "max": max_tiles}
        self._claim(flood, x, y)
        self.floods.append(flood)
        self.engine.memory_manager.add_event(
            "[Realm] Water surges over the banks — the land is "
            "flooding!")
        return True

    def tick(self) -> None:
        if not self.floods:
            self._maybe_storm_flood()
            return
        engine = self.engine
        for flood in list(self.floods):
            flood["turns_left"] -= 1
            if flood["turns_left"] <= 0:
                self._recede(flood)
                self.floods.remove(flood)
                continue
            if engine.turn_counter % SPREAD_INTERVAL == 0:
                self._spread(flood)

    # ------------------------------------------------------- internals

    def _claim(self, flood, x: int, y: int) -> bool:
        """Drown one tile if it is low, dry, and empty."""
        wmap = self.engine.world.map
        terrain = wmap.terrain[y][x]
        if terrain not in FLOODABLE:
            return False
        if wmap.get_character_at(x, y) is not None:
            return False           # the water laps around them
        flood["flooded"].append([x, y, terrain.value])
        wmap.set_terrain(x, y, TerrainType.WATER)
        return True

    def _spread(self, flood) -> None:
        wmap = self.engine.world.map
        new_frontier = []
        for fx, fy in flood["frontier"]:
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                if len(flood["flooded"]) >= flood["max"]:
                    flood["frontier"] = new_frontier
                    return
                nx, ny = fx + dx, fy + dy
                if not (0 <= nx < wmap.width and
                        0 <= ny < wmap.height):
                    continue
                if wmap.terrain[ny][nx] == TerrainType.WATER:
                    continue
                if self._claim(flood, nx, ny):
                    new_frontier.append([nx, ny])
        flood["frontier"] = new_frontier

    def _recede(self, flood) -> None:
        wmap = self.engine.world.map
        for x, y, orig in flood["flooded"]:
            if wmap.terrain[y][x] == TerrainType.WATER:
                wmap.set_terrain(x, y, TerrainType(orig))
        self.engine.memory_manager.add_event(
            "[Realm] The floodwaters recede, leaving the land "
            "sodden but whole.")

    def _maybe_storm_flood(self) -> None:
        try:
            from world.weather import Weather
            state = self.engine.weather_system.state.current
        except Exception:
            return
        if state != Weather.STORM or \
                self.rng.random() >= STORM_FLOOD_CHANCE:
            return
        wmap = self.engine.world.map
        edges = [(x, y) for y in range(wmap.height)
                 for x in range(wmap.width)
                 if wmap.terrain[y][x] in FLOODABLE
                 and any(0 <= x + dx < wmap.width
                         and 0 <= y + dy < wmap.height
                         and wmap.terrain[y + dy][x + dx] ==
                         TerrainType.WATER
                         for dx, dy in ((1, 0), (-1, 0),
                                        (0, 1), (0, -1)))]
        if edges:
            x, y = self.rng.choice(edges)
            self.start_flood(x, y)

    # ---------------------------------------------------- persistence

    def to_dict(self) -> dict:
        return {"floods": self.floods}

    def from_dict(self, data: dict) -> None:
        self.floods = data.get("floods", [])
