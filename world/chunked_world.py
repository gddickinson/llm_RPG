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
    # a region's NPCs travel WITH the region, not with the player — each
    # region keeps its own cast so the same villagers don't reappear in
    # the next map over.
    cached_npcs: Dict[Tuple[int, int], list] = field(default_factory=dict)
    # dropped loot & bodies belong to their region too (bug-fix 2026-07-12):
    # keyed by (x,y), they used to bleed into the next map at the same coords.
    cached_ground_items: Dict[Tuple[int, int], dict] = field(default_factory=dict)
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
        # party members cross with the player (they were cleared off the
        # old grid) — set them beside the player to fan out next turn
        for nid in self._party_ids():
            npc = self.engine.npc_manager.get_npc(nid)
            if npc is not None:
                npc.position = (new_x, new_y)
                self.engine.world.map.place_character(npc, new_x, new_y)
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
        # stow this region's dropped loot & bodies, then clear the world's
        # so they don't reappear in the next map (bug-fix 2026-07-12)
        world = self.engine.world
        self.cw.cached_ground_items[(rx, ry)] = dict(
            getattr(world, "ground_items", {}) or {})
        world.ground_items = {}
        # stow this region's cast and pull them OUT of the live manager,
        # so they don't bleed into the next region we walk into.
        self.cw.cached_npcs[(rx, ry)] = self._pop_region_npcs()

    def _party_ids(self) -> set:
        """The NPC ids that follow the player (companions), not the
        region — read from the companion manager."""
        cm = getattr(self.engine, "companion_manager", None)
        ids = set(getattr(cm, "party", []) or []) if cm else set()
        ids |= set(getattr(self.engine, "party", []) or [])
        return ids

    def _pop_region_npcs(self) -> list:
        """Remove every non-player, non-party NPC from the manager and
        return them. Party members travel with the player, so they stay."""
        party = self._party_ids()
        nm = self.engine.npc_manager
        leaving = [npc for nid, npc in list(nm.npcs.items())
                   if nid not in party]
        for npc in leaving:
            nm.remove_npc(npc.id)
        return leaving

    def _restore(self, rx: int, ry: int) -> None:
        terrain = self.cw.cached_terrain[(rx, ry)]
        locations = self.cw.cached_locations[(rx, ry)]
        self.engine.world.map.terrain = [list(row) for row in terrain]
        self.engine.world.locations = list(locations)
        # this region's own dropped loot & bodies come back with it
        self.engine.world.ground_items = dict(
            self.cw.cached_ground_items.get((rx, ry), {}))
        self._reset_map_characters()
        # bring this region's own cast back to life at their old posts
        for npc in self.cw.cached_npcs.get((rx, ry), []):
            self.engine.npc_manager.add_npc(npc)
            pos = getattr(npc, "position", None)
            if pos:
                self.engine.world.map.place_character(npc, *pos)
        self._rebuild_interiors()

    def _generate(self, rx: int, ry: int) -> None:
        plan = self.cw.plan_for(rx, ry)
        from world.world_generator import WorldGenerator
        # Wipe world state — a fresh region starts with no dropped loot
        self.engine.world.locations = []
        self.engine.world.ground_items = {}
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
        if plan.flavor != "home":
            self._seed_landmarks(rx, ry, plan.seed)   # named places (P21.5)
        self._reset_map_characters()
        self._rebuild_interiors()

    def _seed_landmarks(self, rx: int, ry: int, seed: int) -> None:
        """Off-origin regions get named LANDMARKS instead of empty noise
        (P21.5): a ruin, a shrine, a dark hollow that leads underground —
        deterministic per region so the map is stable, drawn from
        `data/landmarks.json` and placed on terrain that suits them."""
        import random
        from items.data_loader import load_data_file
        from world.location import Location
        from world.world_map import TerrainType
        try:
            defs = load_data_file("landmarks.json")
        except Exception:
            defs = {}
        if not defs:
            return
        rng = random.Random((seed or 0) ^ 0x1A4D)
        wmap = self.engine.world.map
        keys = list(defs.keys())
        placed, tries = 0, 0
        want_count = rng.randint(1, 2)
        while placed < want_count and tries < 240:
            tries += 1
            spec = defs[rng.choice(keys)]
            x = rng.randint(3, wmap.width - 4)
            y = rng.randint(3, wmap.height - 4)
            if wmap.terrain[y][x].value not in spec.get("terrain", []):
                continue
            if self.engine.world.get_location_at(x, y) is not None:
                continue
            if spec.get("tile") == "cave":
                wmap.terrain[y][x] = TerrainType.CAVE
            loc = Location(spec["name"], spec.get("description", ""),
                           x, y, 1, 1)
            loc.add_property("landmark", True)
            self.engine.world.add_location(loc)
            placed += 1

    def _reset_map_characters(self) -> None:
        wmap = self.engine.world.map
        wmap.characters = {}

    def _rebuild_interiors(self) -> None:
        try:
            from world.interiors import build_interiors_for_world
            self.engine.interiors = build_interiors_for_world(self.engine.world)
        except Exception:
            pass
