"""Tests for the larger world + second settlement (Bundle B)."""

import unittest

from engine.game_engine import GameEngine


class TestLargerWorld(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_world_is_120x80(self):
        self.assertEqual(self.engine.world.map.width, 120)
        self.assertEqual(self.engine.world.map.height, 80)

    def test_riverside_hamlet_exists(self):
        names = [l.name for l in self.engine.world.locations]
        self.assertIn("Riverside Hamlet", names)
        self.assertIn("Riverside Inn", names)
        self.assertIn("Hamlet Chapel", names)

    def test_oakvale_still_exists(self):
        names = [l.name for l in self.engine.world.locations]
        self.assertIn("Oakvale Village", names)
        self.assertIn("Oakvale Tavern", names)

    def test_stonepine_camp_exists(self):
        # Third settlement appears on maps >= 100x60
        names = [l.name for l in self.engine.world.locations]
        self.assertIn("Stonepine Camp", names)
        self.assertIn("Foreman's Hall", names)
        self.assertIn("Stonepine Smithy", names)
        self.assertIn("Camp Tavern", names)

    def test_second_cave_exists(self):
        names = [l.name for l in self.engine.world.locations]
        self.assertIn("Goblin Warrens", names)

    def test_hamlet_npcs(self):
        npcs = self.engine.npc_manager.npcs
        self.assertIn("hamlet_innkeeper_01", npcs)
        self.assertIn("hamlet_priest_01", npcs)
        self.assertIn("hamlet_wheelwright_01", npcs)

    def test_camp_npcs(self):
        npcs = self.engine.npc_manager.npcs
        self.assertIn("camp_foreman_01", npcs)
        self.assertIn("camp_smith_01", npcs)
        self.assertIn("camp_taverner_01", npcs)


if __name__ == "__main__":
    unittest.main()
