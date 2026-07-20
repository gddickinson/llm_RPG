"""George: combine the start-menu worlds into ONE larger world with a single
entry point. `world_kind="combined"` plants the big Oakvale town + the
Bloodstone Castle + the wilds on one expanded map, entered at Oakvale."""

import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from engine.game_engine import GameEngine


class TestCombinedWorld(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.e = GameEngine(llm_provider="heuristic",
                           enable_npc_processes=False, world_kind="combined")
        cls.e.start_game()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.e.end_game()
        except Exception:
            pass

    def _names(self):
        return [l.name for l in self.e.world.locations]

    def test_map_is_expanded(self):
        wm = self.e.world.map
        # bigger than the old oakvale region (190x140) and default (120x80)
        self.assertGreaterEqual(wm.width, 200)
        self.assertGreaterEqual(wm.height, 160)

    def test_town_castle_and_wilds_share_one_map(self):
        names = self._names()
        self.assertTrue(any("Oakvale" in n for n in names))
        self.assertTrue(any("Bloodstone" in n for n in names))
        # the seeded systems all populate the one world
        self.assertGreaterEqual(
            sum(1 for l in self.e.world.locations
                if l.get_property("waystone")), 1)
        self.assertGreaterEqual(len(getattr(self.e.lairs, "lairs", [])), 1)

    def test_single_entry_point_at_oakvale(self):
        # the hero wakes on the Oakvale arrival waystone (near the map centre)
        wm = self.e.world.map
        px, py = self.e.player.position
        self.assertLess(abs(px - wm.width // 2), wm.width // 3)
        self.assertLess(abs(py - wm.height // 2), wm.height // 3)

    def test_castle_is_enterable(self):
        castle = next((l for l in self.e.world.locations
                       if "Bloodstone" in l.name), None)
        self.assertIsNotNone(castle)
        # the P18 castle structure attaches to its Location
        self.assertIn(castle.name, self.e.interiors)

    def test_size_helper(self):
        from world.town_region import region_size
        self.assertIsNotNone(region_size("combined"))
        self.assertIsNone(region_size("default"))


if __name__ == "__main__":
    unittest.main()
