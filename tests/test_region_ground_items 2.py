"""Region ground items stay in their region (bug-fix 2026-07-12, P25.0).

Dropped treasure and KO'd bodies used to bleed into the next region at the
same coordinates, because the streamer cached terrain / locations / NPCs
per region but never `world.ground_items`. Now they travel with the region."""

import os as _os
import tempfile as _tempfile
_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_reg_"))

import unittest

from engine.game_engine import GameEngine
from items.item_registry import create_item


def _count(world):
    return sum(len(v) for v in getattr(world, "ground_items", {}).values())


class TestRegionGroundItems(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False)
        self.engine.start_game()
        self.ws = self.engine.world_streamer
        self.world = self.engine.world

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _drop_marker(self):
        self.world.add_item_to_ground(create_item("greater_potion"), 30, 20)
        self.world.add_item_to_ground("A fallen raider's body", 31, 20)

    def test_dropped_loot_does_not_bleed_into_a_new_region(self):
        self._drop_marker()
        self.assertIn((30, 20), self.world.ground_items)
        self.ws.transit("east")            # into a freshly-generated region
        self.assertNotIn((30, 20), self.world.ground_items,
                         "treasure must not follow you across the border")
        self.assertNotIn((31, 20), self.world.ground_items,
                         "nor the body")

    def test_a_regions_items_return_when_you_come_back(self):
        self._drop_marker()
        before = _count(self.world)
        self.ws.transit("east")
        self.ws.transit("west")            # back home
        self.assertEqual(_count(self.world), before,
                         "the home region's loot is exactly as you left it")
        self.assertIn((30, 20), self.world.ground_items)

    def test_a_fresh_region_starts_empty_of_dropped_loot(self):
        self._drop_marker()
        self.ws.transit("north")
        # nothing the player dropped at home is here
        here = self.world.ground_items
        self.assertNotIn((30, 20), here)
        self.assertNotIn((31, 20), here)

    def test_items_dropped_in_a_new_region_stay_there(self):
        self.ws.transit("east")
        self.world.add_item_to_ground(create_item("coins"), 10, 10)
        self.ws.transit("west")            # home has its own loot, not this
        self.assertNotIn((10, 10), self.world.ground_items)
        self.ws.transit("east")            # back to where we dropped it
        self.assertIn((10, 10), self.world.ground_items,
                      "loot waits in the region it was dropped in")


if __name__ == "__main__":
    unittest.main()
