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
        # pin the P12.1 quality roll to a plain success
        self.engine.forage_manager.rng.randint = lambda a, b: 10
        before = len(self.engine.player.inventory)
        msg = self.engine.forage()
        self.assertIn("forage", msg.lower())
        self.assertGreater(len(self.engine.player.inventory), before)

    def test_water_teaches_fishing_instead_of_foraging(self):
        # Water became a fishing node in P2.2: Z without a rod should
        # teach the tool requirement, not claim there's nothing here.
        spot = self._find_terrain(TerrainType.WATER)
        if not spot:
            self.skipTest("no water tile")
        self.engine.player.position = spot
        msg = self.engine.forage()
        self.assertIn("fishing rod", msg.lower())

    def test_cooldown(self):
        spot = self._find_terrain(TerrainType.FOREST)
        self.engine.player.position = spot
        self.engine.forage_manager.rng.randint = lambda a, b: 10
        msg1 = self.engine.forage()
        self.assertIn("forage", msg1.lower())
        msg2 = self.engine.forage()
        self.assertIn("recently", msg2.lower())


if __name__ == "__main__":
    unittest.main()


class TestForageFatigue(unittest.TestCase):
    """PT3.1 finding: fresh-tile hopping was an economy breaker."""

    def setUp(self):
        from engine.game_engine import GameEngine
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_daily_yield_thins(self):
        from world.world_map import TerrainType
        e = self.engine
        p, wmap = e.player, e.world.map
        got = tries = 0
        for y in range(wmap.height):
            for x in range(wmap.width):
                if tries >= 150:
                    break
                if wmap.get_terrain_at(x, y) == TerrainType.FOREST \
                        and wmap.get_character_at(x, y) is None:
                    wmap.remove_character(p)
                    p.position = (x, y)
                    wmap.place_character(p, x, y)
                    if "You forage and find" in e.forage():
                        got += 1
                    tries += 1
            if tries >= 150:
                break
        self.assertLess(got, 80,
                        "daily forage fatigue must cap the harvest")
        self.assertGreater(got, 5, "but foraging must still work")

    def test_a_new_day_restores_the_eye(self):
        e = self.engine
        e.player.metadata["forage_day"] = 0
        e.player.metadata["forage_count"] = 999
        e.world.time += 24 * 60
        # next forage resets the counter
        from world.world_map import TerrainType
        wmap = e.world.map
        for y in range(wmap.height):
            for x in range(wmap.width):
                if wmap.get_terrain_at(x, y) == TerrainType.FOREST \
                        and wmap.get_character_at(x, y) is None:
                    wmap.remove_character(e.player)
                    e.player.position = (x, y)
                    wmap.place_character(e.player, x, y)
                    e.forage()
                    self.assertLessEqual(
                        e.player.metadata["forage_count"], 1)
                    return
