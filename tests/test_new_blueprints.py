"""Tests for the expanded blueprint library + new wilderness buildings."""

import unittest

from world.blueprints import BLUEPRINT_LIBRARY, blueprint_for_location
from engine.game_engine import GameEngine


class TestNewBlueprints(unittest.TestCase):
    def test_new_keys_present(self):
        for key in ("watchtower", "farmhouse", "stable", "library", "stall",
                    "well", "tower", "lodge", "shrine"):
            self.assertIn(key, BLUEPRINT_LIBRARY, key)

    def test_lookup_resolves_new_names(self):
        self.assertIsNotNone(blueprint_for_location("Oakvale Watchtower"))
        self.assertIsNotNone(blueprint_for_location("Old Farmhouse"))
        self.assertIsNotNone(blueprint_for_location("Stable"))
        self.assertIsNotNone(blueprint_for_location("Wizard's Tower"))
        self.assertIsNotNone(blueprint_for_location("Hunter's Lodge"))
        self.assertIsNotNone(blueprint_for_location("Wayside Shrine"))
        self.assertIsNotNone(blueprint_for_location("Oakvale Market Stall"))


class TestExtraWorldBuildings(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_watchtower_in_world(self):
        names = [l.name for l in self.engine.world.locations]
        self.assertTrue(any("Watchtower" in n for n in names))

    def test_some_wilderness_buildings_placed(self):
        # At least one of: Hunter's Lodge, Farmhouse, Wayside Shrine,
        # Wizard's Tower
        names = [l.name for l in self.engine.world.locations]
        wilderness_buildings = [n for n in names if any(
            kw in n for kw in ("Lodge", "Farmhouse", "Shrine",
                                "Wizard's Tower", "Stable",
                                "Abandoned Watchtower"))]
        self.assertGreater(len(wilderness_buildings), 0,
                           f"no wilderness buildings placed: {names}")


if __name__ == "__main__":
    unittest.main()
