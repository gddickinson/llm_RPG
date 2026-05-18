"""Tests for foraging."""

import unittest

from engine.game_engine import GameEngine
from world.world_map import TerrainType


class TestForaging(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _find_terrain(self, target):
        wmap = self.engine.world.map
        for y in range(wmap.height):
            for x in range(wmap.width):
                if wmap.terrain[y][x] == target:
                    return (x, y)
        return None

    def test_forage_in_forest(self):
        spot = self._find_terrain(TerrainType.FOREST)
        self.assertIsNotNone(spot)
        self.engine.player.position = spot
        before = len(self.engine.player.inventory)
        msg = self.engine.forage()
        self.assertIn("forage", msg.lower())
        self.assertGreater(len(self.engine.player.inventory), before)

    def test_no_forage_on_water(self):
        spot = self._find_terrain(TerrainType.WATER)
        if not spot:
            self.skipTest("no water tile")
        self.engine.player.position = spot
        msg = self.engine.forage()
        self.assertIn("nothing", msg.lower())

    def test_cooldown(self):
        spot = self._find_terrain(TerrainType.FOREST)
        self.engine.player.position = spot
        msg1 = self.engine.forage()
        self.assertIn("forage", msg1.lower())
        msg2 = self.engine.forage()
        self.assertIn("recently", msg2.lower())


if __name__ == "__main__":
    unittest.main()
