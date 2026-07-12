"""Ground items stay on their floor (bug-fix 2026-07-12).

Items dropped inside a building appeared on EVERY level, because
`world.ground_items` was one flat (x,y) dict and floors reuse
coordinates. Now each zone owns its item store and `world.ground_items`
points at the active grid, so a potion dropped in the cellar stays in the
cellar."""

import os as _os
import tempfile as _tempfile
_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_zgi_"))

import types
import unittest

from engine.game_engine import GameEngine
from items.item_registry import create_item


def _count(d):
    return sum(len(v) for v in (d or {}).values())


class _Base(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False)
        self.engine.start_game()
        self.world = self.engine.world

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass


class TestSync(_Base):
    def test_entering_a_zone_parks_the_overworld_items(self):
        self.world.add_item_to_ground(create_item("coins"), 40, 30)
        n = _count(self.world.ground_items)
        z1 = types.SimpleNamespace(name="z1", ground_items=None)
        self.engine.current_interior = z1
        self.engine._sync_ground_items()
        self.assertEqual(_count(self.world.ground_items), 0,
                         "the overworld loot is not in the zone")
        self.assertEqual(_count(self.world._overworld_ground_items), n,
                         "it is parked")

    def test_two_floors_do_not_share_items(self):
        z1 = types.SimpleNamespace(name="floor1", ground_items=None)
        z2 = types.SimpleNamespace(name="floor2", ground_items=None)
        self.engine.current_interior = z1
        self.engine._sync_ground_items()
        self.world.add_item_to_ground(create_item("greater_potion"), 3, 4)
        self.assertEqual(_count(self.world.ground_items), 1)
        # climb to floor 2
        self.engine.current_interior = z2
        self.engine._sync_ground_items()
        self.assertEqual(_count(self.world.ground_items), 0,
                         "floor 2 does not show floor 1's drop")
        # back to floor 1
        self.engine.current_interior = z1
        self.engine._sync_ground_items()
        self.assertEqual(_count(self.world.ground_items), 1,
                         "floor 1 kept its drop")

    def test_leaving_restores_the_overworld(self):
        self.world.add_item_to_ground(create_item("coins"), 40, 30)
        z1 = types.SimpleNamespace(name="z1", ground_items=None)
        self.engine.current_interior = z1
        self.engine._sync_ground_items()
        self.world.add_item_to_ground(create_item("bread"), 2, 2)  # in the zone
        self.engine.current_interior = None
        self.engine._sync_ground_items()
        self.assertIn((40, 30), self.world.ground_items)
        self.assertNotIn((2, 2), self.world.ground_items,
                         "the zone drop did not bleed onto the overworld")


class TestIntegration(_Base):
    def test_entering_a_real_building_isolates_drops(self):
        loc = next((l for l in self.world.locations
                    if l.name in self.engine.interiors), None)
        if loc is None:
            self.skipTest("no enterable building")
        self.world.add_item_to_ground(create_item("coins"), 41, 31)
        overworld_n = _count(self.world.ground_items)
        self.engine.enter_building(loc)
        pos = self.engine.player.position
        self.world.add_item_to_ground(create_item("greater_potion"), *pos)
        self.engine.exit_building()
        self.assertEqual(_count(self.world.ground_items), overworld_n,
                         "the drop inside stayed inside")


class TestSaveSafety(_Base):
    def test_a_zone_save_keeps_overworld_items_separate(self):
        # the save reads the parked overworld dict when you save in a zone,
        # so overworld loot isn't clobbered and zone drops aren't promoted
        self.world.add_item_to_ground(create_item("coins"), 40, 30)
        z1 = types.SimpleNamespace(name="z1", ground_items=None)
        self.engine.current_interior = z1
        self.engine._sync_ground_items()
        self.world.add_item_to_ground(create_item("bread"), 2, 2)
        parked = self.world._overworld_ground_items
        self.assertIn((40, 30), parked)
        self.assertNotIn((2, 2), parked, "zone drops aren't overworld items")


if __name__ == "__main__":
    unittest.main()
