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

    def test_oakvale_is_walled_with_gates(self):
        oak = self._oak()
        gates = oak.get_property("gates")
        self.assertTrue(gates, "the start town should record its gates")
        wmap = self.engine.world.map
        x0, y0, x1, y1 = fortify.town_bounds(oak, 2)
        walls = sum(
            1 for x in range(x0, x1 + 1) for y in (y0, y1)
            if 0 <= x < wmap.width and 0 <= y < wmap.height
            and wmap.terrain[y][x] == TerrainType.BUILDING)
        self.assertGreater(walls, 4, "a real wall rings the town")

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
        oak = self._oak()
        x0, y0, x1, y1 = fortify.town_bounds(oak, 2)

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


if __name__ == "__main__":
    unittest.main()
