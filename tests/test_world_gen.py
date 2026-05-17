"""Tests for procedural world generation."""

import unittest

from world.world import World
from world.world_map import TerrainType
from world.world_generator import WorldGenerator


class TestWorldGenerator(unittest.TestCase):
    def setUp(self):
        self.world = World(width=30, height=20)
        WorldGenerator(self.world, seed=7).generate()

    def test_size_intact(self):
        self.assertEqual(self.world.map.width, 30)
        self.assertEqual(self.world.map.height, 20)

    def test_has_water(self):
        found = any(self.world.map.terrain[y][x] == TerrainType.WATER
                    for y in range(self.world.map.height)
                    for x in range(self.world.map.width))
        self.assertTrue(found)

    def test_has_road(self):
        found = any(self.world.map.terrain[y][x] == TerrainType.ROAD
                    for y in range(self.world.map.height)
                    for x in range(self.world.map.width))
        self.assertTrue(found)

    def test_has_mountain(self):
        found = any(self.world.map.terrain[y][x] == TerrainType.MOUNTAIN
                    for y in range(self.world.map.height)
                    for x in range(self.world.map.width))
        self.assertTrue(found)

    def test_has_buildings(self):
        found = any(self.world.map.terrain[y][x] == TerrainType.BUILDING
                    for y in range(self.world.map.height)
                    for x in range(self.world.map.width))
        self.assertTrue(found)

    def test_named_locations(self):
        names = [l.name for l in self.world.locations]
        self.assertIn("Oakvale Village", names)
        self.assertIn("Dark Cave", names)

    def test_determinism(self):
        a = World(width=30, height=20)
        WorldGenerator(a, seed=7).generate()
        b = World(width=30, height=20)
        WorldGenerator(b, seed=7).generate()
        self.assertEqual(a.map.terrain, b.map.terrain)


if __name__ == "__main__":
    unittest.main()
