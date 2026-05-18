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

    def test_world_is_60x40(self):
        self.assertEqual(self.engine.world.map.width, 60)
        self.assertEqual(self.engine.world.map.height, 40)

    def test_riverside_hamlet_exists(self):
        names = [l.name for l in self.engine.world.locations]
        self.assertIn("Riverside Hamlet", names)
        self.assertIn("Riverside Inn", names)
        self.assertIn("Hamlet Chapel", names)

    def test_oakvale_still_exists(self):
        names = [l.name for l in self.engine.world.locations]
        self.assertIn("Oakvale Village", names)
        self.assertIn("Oakvale Tavern", names)

    def test_hamlet_npcs(self):
        # Innkeeper, priest, wheelwright
        npcs = self.engine.npc_manager.npcs
        self.assertIn("hamlet_innkeeper_01", npcs)
        self.assertIn("hamlet_priest_01", npcs)
        self.assertIn("hamlet_wheelwright_01", npcs)


if __name__ == "__main__":
    unittest.main()
