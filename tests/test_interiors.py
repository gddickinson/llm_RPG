"""Tests for building interiors."""

import unittest

from engine.game_engine import GameEngine
from world.interiors import (
    Interior, make_tavern_interior, make_forge_interior,
    build_interiors_for_world,
)


class TestInteriors(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_interiors_built(self):
        self.assertGreater(len(self.engine.interiors), 0)
        # Should include tavern, forge, store, temple
        names = list(self.engine.interiors.keys())
        self.assertTrue(any("Tavern" in n for n in names))
        self.assertTrue(any("Forge" in n for n in names))

    def test_tavern_interior_grid(self):
        inter = make_tavern_interior()
        # Walls on edges
        from world.world_map import TerrainType
        self.assertEqual(inter.terrain[0][0], TerrainType.BUILDING)
        self.assertEqual(inter.terrain[-1][-1], TerrainType.BUILDING)
        # Door open
        dx, dy = inter.door
        self.assertEqual(inter.terrain[dy][dx], TerrainType.ROAD)
        # Has furniture
        self.assertTrue(inter.furniture)

    def test_enter_and_exit(self):
        # Move player to tavern
        for loc in self.engine.world.locations:
            if "Tavern" in loc.name:
                cx, cy = loc.center()
                self.engine.world.map.remove_character(self.engine.player)
                self.engine.player.position = (cx, cy)
                self.engine.world.map.place_character(self.engine.player, cx, cy)
                break
        msg = self.engine.enter_building()
        self.assertIn("enter", msg.lower())
        self.assertIsNotNone(self.engine.current_interior)
        msg = self.engine.exit_building()
        self.assertIn("leave", msg.lower())
        self.assertIsNone(self.engine.current_interior)


if __name__ == "__main__":
    unittest.main()
