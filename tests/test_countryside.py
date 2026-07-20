"""OAKVALE T7 — terrain-aware roads + the living countryside."""

import unittest

from world.world import World
from world.world_map import TerrainType
from world import road_astar


class TestRoadAstar(unittest.TestCase):
    def _grass_world(self, w=40, h=20):
        world = World(w, h)
        for y in range(h):
            for x in range(w):
                world.map.terrain[y][x] = TerrainType.GRASS
        return world

    def test_path_connects_two_points(self):
        wm = self._grass_world().map
        path = road_astar.find_road_path(wm, (2, 10), (30, 10))
        self.assertIsNotNone(path)
        self.assertEqual(path[0], (2, 10))
        self.assertEqual(path[-1], (30, 10))

    def test_lay_road_bridges_water(self):
        world = self._grass_world()
        wm = world.map
        for y in range(20):                          # a river down the middle
            wm.terrain[y][15] = TerrainType.WATER
        bridges = road_astar.connect(wm, (2, 10), (30, 10))
        self.assertGreaterEqual(bridges, 1, "the road bridges the river")
        self.assertEqual(wm.terrain[10][15], TerrainType.BRIDGE)

    def test_road_prefers_grass_over_mountain(self):
        world = self._grass_world(30, 30)
        wm = world.map
        for y in range(8, 22):                        # a mountain wall with a gap
            for x in range(12, 18):
                wm.terrain[y][x] = TerrainType.MOUNTAIN
        path = road_astar.find_road_path(wm, (2, 15), (28, 15))
        self.assertIsNotNone(path)
        mount = sum(1 for (x, y) in path
                    if wm.terrain[y][x] == TerrainType.MOUNTAIN)
        # it should route around most of the mountain, not bore through it
        self.assertLessEqual(mount, 3)

    def test_never_routes_through_a_building(self):
        world = self._grass_world()
        wm = world.map
        for y in range(20):
            if y != 10:                               # a wall with one gap? no —
                wm.terrain[y][15] = TerrainType.BUILDING
        # a full building wall except a gap at y=10 → path must use the gap
        path = road_astar.find_road_path(wm, (2, 10), (30, 10))
        self.assertIsNotNone(path)
        for (x, y) in path:
            self.assertNotEqual(wm.terrain[y][x], TerrainType.BUILDING)


class TestCountrysideIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from engine.game_engine import GameEngine
        cls.engine = GameEngine(llm_provider="heuristic",
                                enable_npc_processes=False,
                                world_kind="oakvale")
        cls.engine.start_game()
        cls.wm = cls.engine.world.map

    @classmethod
    def tearDownClass(cls):
        try:
            cls.engine.end_game()
        except Exception:
            pass

    def test_supporting_villages_exist(self):
        villages = [l for l in self.engine.world.locations
                    if l.get_property("village")]
        self.assertGreaterEqual(len(villages), 2, "a hinterland of villages")

    def test_farmland_and_bridges(self):
        farms = sum(1 for row in self.wm.terrain
                    for t in row if t == TerrainType.FARMLAND)
        bridges = sum(1 for row in self.wm.terrain
                      for t in row if t == TerrainType.BRIDGE)
        self.assertGreater(farms, 100, "fields worked around the town")
        self.assertGreater(bridges, 0, "roads bridge the river")

    def test_farmers_work_the_land(self):
        farmers = [n for n in self.engine.npc_manager.npcs.values()
                   if n.metadata.get("role") == "Farmer"]
        self.assertGreater(len(farmers), 5)


if __name__ == "__main__":
    unittest.main()
