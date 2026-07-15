"""P31.1 — a walled, guarded start town.

The starting town (Oakvale) is ringed with a curtain wall, gates cut where
the roads cross, and a guard posted at each gate — a defensible, monster-free
town (P27.1 already keeps wandering spawns out of its environs). Pure geometry
in `world/fortify.py`, plus the live-world wiring.
"""

import unittest
from collections import deque

from engine.game_engine import GameEngine
from world.world_map import WorldMap, TerrainType
from world.location import Location
from world import fortify


def _grass_map(w=24, h=24):
    m = WorldMap(w, h)
    for y in range(h):
        for x in range(w):
            m.terrain[y][x] = TerrainType.GRASS
    return m


class TestFortifyGeometry(unittest.TestCase):
    def _town(self):
        return Location("Town", "", 8, 8, 4, 3)

    def test_the_perimeter_is_walled(self):
        m = _grass_map()
        loc = self._town()
        fortify.fortify(m, loc, margin=2)
        x0, y0, x1, y1 = fortify.town_bounds(loc, 2)
        self.assertEqual(m.terrain[y0][x0], TerrainType.BUILDING)   # a corner
        self.assertEqual(m.terrain[y1][x1], TerrainType.BUILDING)

    def test_the_interior_is_untouched(self):
        m = _grass_map()
        loc = self._town()
        fortify.fortify(m, loc, margin=2)
        self.assertEqual(m.terrain[loc.y + 1][loc.x + 1], TerrainType.GRASS)

    def test_a_road_crossing_becomes_a_gate(self):
        m = _grass_map()
        loc = self._town()
        x0, y0, x1, y1 = fortify.town_bounds(loc, 2)
        midx = (x0 + x1) // 2
        for y in range(m.height):            # a road down the middle column
            m.terrain[y][midx] = TerrainType.ROAD
        gates = fortify.fortify(m, loc, margin=2)
        self.assertIn((midx, y0), gates)
        self.assertIn((midx, y1), gates)
        self.assertEqual(m.terrain[y0][midx], TerrainType.ROAD)     # passable

    def test_no_road_cuts_exactly_one_gate(self):
        m = _grass_map()
        loc = self._town()
        gates = fortify.fortify(m, loc, margin=2)
        self.assertEqual(len(gates), 1)
        gx, gy = gates[0]
        self.assertEqual(m.terrain[gy][gx], TerrainType.ROAD)

    def test_water_on_the_perimeter_is_left_as_a_barrier(self):
        m = _grass_map()
        loc = self._town()
        x0, y0, x1, y1 = fortify.town_bounds(loc, 2)
        m.terrain[y0][x0 + 1] = TerrainType.WATER
        fortify.fortify(m, loc, margin=2)
        self.assertEqual(m.terrain[y0][x0 + 1], TerrainType.WATER)

    def test_extent_bounds_several_locations(self):
        # P31.1b: the box grows to enclose every member + a margin
        a = Location("A", "", 8, 8, 2, 2)
        b = Location("B", "", 14, 12, 3, 2)      # off to the SE
        x0, y0, x1, y1 = fortify.extent([a, b], margin=2)
        self.assertEqual((x0, y0), (6, 6))       # min corner - margin
        self.assertEqual((x1, y1), (18, 15))     # max corner + margin


class TestWalledStartTown(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False)
        self.engine.start_game()

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _oak(self):
        return next(l for l in self.engine.world.locations
                    if l.name == "Oakvale Village")

    def _box(self):
        """The actual wall box, from the stored corner towers (P31.1b)."""
        corners = self._oak().get_property("towers")
        xs = [c[0] for c in corners]
        ys = [c[1] for c in corners]
        return min(xs), min(ys), max(xs), max(ys)

    def test_oakvale_is_walled_with_gates(self):
        oak = self._oak()
        self.assertTrue(oak.get_property("gates"), "records its gates")
        wmap = self.engine.world.map
        x0, y0, x1, y1 = self._box()
        walls = sum(
            1 for x in range(x0, x1 + 1) for y in (y0, y1)
            if 0 <= x < wmap.width and 0 <= y < wmap.height
            and wmap.terrain[y][x] == TerrainType.BUILDING)
        self.assertGreater(walls, 8, "a real wall rings the whole town")

    def test_the_wall_encompasses_the_library(self):
        # P31.1b: the wall reaches out to include the library + civic buildings
        oak = self._oak()
        x0, y0, x1, y1 = self._box()
        lib = next((l for l in self.engine.world.locations
                    if "library" in l.name.lower()), None)
        if lib is None:
            self.skipTest("no library in this world")
        self.assertTrue(x0 <= lib.x <= x1 and y0 <= lib.y <= y1,
                        "the library sits inside the town wall")

    def test_corner_towers_are_manned(self):
        oak = self._oak()
        self.assertEqual(len(oak.get_property("towers")), 4)
        towers = [l for l in self.engine.world.locations
                  if (l.properties or {}).get("wall_tower")]
        self.assertEqual(len(towers), 4, "a tower at each corner")
        guards = [n for n in self.engine.npc_manager.npcs.values()
                  if (getattr(n, "metadata", {}) or {}).get("tower_guard")]
        self.assertGreaterEqual(len(guards), 1, "a guard mans a tower")

    def test_gates_are_passable(self):
        wmap = self.engine.world.map
        for gx, gy in self._oak().get_property("gates"):
            self.assertIn(wmap.terrain[gy][gx],
                          (TerrainType.ROAD, TerrainType.BRIDGE))

    def test_guards_stand_at_the_gates(self):
        guards = [n for n in self.engine.npc_manager.npcs.values()
                  if (getattr(n, "metadata", {}) or {}).get("gate_guard")]
        self.assertGreaterEqual(len(guards), 1)

    def test_the_player_is_not_trapped(self):
        wmap = self.engine.world.map
        x0, y0, x1, y1 = self._box()

        def walkable(x, y):
            return (0 <= x < wmap.width and 0 <= y < wmap.height
                    and wmap.terrain[y][x] not in (
                        TerrainType.BUILDING, TerrainType.WATER,
                        TerrainType.MOUNTAIN))

        start = tuple(self.engine.player.position)
        seen, q, escaped = {start}, deque([start]), False
        while q:
            cx, cy = q.popleft()
            if not (x0 <= cx <= x1 and y0 <= cy <= y1):
                escaped = True
                break
            for dx, dy in ((0, 1), (0, -1), (1, 0), (-1, 0)):
                n = (cx + dx, cy + dy)
                if n not in seen and walkable(*n):
                    seen.add(n)
                    q.append(n)
        self.assertTrue(escaped, "the player can leave the walled town")

    def test_town_has_gates_on_at_least_two_sides(self):
        # P37: a walled town is never a one-door prison — when only one road
        # crosses, a second gate is cut on another wall, so an exit is findable.
        gates = self._oak().get_property("gates")
        self.assertGreaterEqual(len(gates), 2, "at least two ways out")
        x0, y0, x1, y1 = self._box()
        sides = set()
        for gx, gy in gates:
            if gy <= y0:
                sides.add("N")
            elif gy >= y1:
                sides.add("S")
            elif gx <= x0:
                sides.add("W")
            else:
                sides.add("E")
        self.assertGreaterEqual(len(sides), 2, "gates on more than one wall")


if __name__ == "__main__":
    unittest.main()
