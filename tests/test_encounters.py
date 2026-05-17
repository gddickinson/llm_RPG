"""Tests for the random encounters system."""

import unittest
import random

from engine.game_engine import GameEngine


class TestEncounters(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()
        # Force RNG so spawns are deterministic when we want them
        self.engine.encounter_manager.rng = random.Random(1)

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_no_spawn_in_village(self):
        # Player default position should be in/near village; even if
        # wilderness, force player into a building tile (no spawn)
        from world.world_map import TerrainType
        # Find a road or building tile
        for y in range(self.engine.world.map.height):
            for x in range(self.engine.world.map.width):
                if self.engine.world.map.terrain[y][x] == TerrainType.ROAD:
                    self.engine.player.position = (x, y)
                    break
            else:
                continue
            break
        # Force encounter chance high then attempt spawn
        from world import encounters
        original = encounters.ENCOUNTER_CHANCE
        encounters.ENCOUNTER_CHANCE = 1.0
        try:
            msg = self.engine.encounter_manager.maybe_spawn()
            # Road isn't FOREST/GRASS, so should return None
            self.assertIsNone(msg)
        finally:
            encounters.ENCOUNTER_CHANCE = original

    def test_spawn_in_wilderness(self):
        from world.world_map import TerrainType
        # Find a grass/forest tile away from buildings
        for y in range(self.engine.world.map.height):
            for x in range(self.engine.world.map.width):
                if self.engine.world.map.terrain[y][x] == TerrainType.GRASS:
                    self.engine.player.position = (x, y)
                    self.engine.world.map.place_character(
                        self.engine.player, x, y)
                    break
            else:
                continue
            break
        from world import encounters
        original = encounters.ENCOUNTER_CHANCE
        encounters.ENCOUNTER_CHANCE = 1.0
        try:
            msg = self.engine.encounter_manager.maybe_spawn()
            self.assertTrue(msg, "Expected a wilderness spawn")
            self.assertIn("appears", msg)
        finally:
            encounters.ENCOUNTER_CHANCE = original


if __name__ == "__main__":
    unittest.main()
