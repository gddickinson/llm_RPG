"""The pack mule (P15.8b): bought at a stable, it hauls +8 slots, flips
`mounted` for the 2x road pace, and trails a step behind you."""

import os as _os
import tempfile as _tempfile
_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_lib_"))

import unittest

from engine import mount
from engine.carry import capacity, can_carry
from engine.game_engine import GameEngine
from world.location import Location


class TestMule(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False)
        self.engine.start_game()
        self.p = self.engine.player
        # a stable to buy at (the demo world usually has one; ensure it)
        self.stable = next((l for l in self.engine.world.locations
                            if "stable" in l.name.lower()), None)
        if self.stable is None:
            self.stable = Location("The Stable", "Hay and horses.",
                                   6, 6, 3, 3)
            self.engine.world.locations.append(self.stable)
        self.p.position = (self.stable.x, self.stable.y - 1)
        self.p.gold = 300

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_none_at_the_start(self):
        self.assertFalse(mount.has_mule(self.p))

    def test_stable_nearby_only_at_a_stable(self):
        self.assertTrue(mount.stable_nearby(self.engine))
        self.p.position = (self.stable.x + 40, self.stable.y + 40)
        self.assertFalse(mount.stable_nearby(self.engine))

    def test_buying_a_mule_costs_gold_and_grants_it(self):
        g0, cap0 = self.p.gold, capacity(self.p)
        mount.buy_mule(self.engine)
        self.assertTrue(mount.has_mule(self.p))
        self.assertEqual(self.p.gold, g0 - mount.MULE_COST)
        self.assertEqual(capacity(self.p), cap0 + mount.MULE_CARRY)

    def test_the_mule_carries_more(self):
        cap0 = capacity(self.p)
        # fill the pack to the old cap so one more can't be carried
        self.p.inventory = list(range(cap0))
        self.assertFalse(can_carry(self.p))
        mount.buy_mule(self.engine)
        self.assertTrue(can_carry(self.p), "the mule takes the overflow")

    def test_the_mule_flips_mounted_for_road_pace(self):
        self.assertNotEqual(self.p.metadata.get("mounted"), True)
        mount.buy_mule(self.engine)
        self.assertTrue(self.p.metadata.get("mounted"),
                        "roads run at the mounted 2x pace with a mule")

    def test_no_stable_no_sale(self):
        self.p.position = (self.stable.x + 40, self.stable.y + 40)
        mount.buy_mule(self.engine)
        self.assertFalse(mount.has_mule(self.p))

    def test_cannot_afford(self):
        self.p.gold = 10
        mount.buy_mule(self.engine)
        self.assertFalse(mount.has_mule(self.p))

    def test_no_second_mule(self):
        mount.buy_mule(self.engine)
        g = self.p.gold
        mount.buy_mule(self.engine)
        self.assertEqual(self.p.gold, g, "you don't pay twice")

    def test_the_mule_trails_behind(self):
        mount.buy_mule(self.engine)
        before = tuple(self.p.position)
        mount.mule_follow(self.engine, before)      # the player moved from here
        self.p.position = (before[0] + 1, before[1])
        mount.mule_follow(self.engine, before)
        self.assertEqual(mount.mule_position(self.engine), before,
                         "the mule steps onto the tile you just left")

    def test_release_lets_the_mule_go(self):
        mount.buy_mule(self.engine)
        mount.release_mule(self.engine)
        self.assertFalse(mount.has_mule(self.p))
        self.assertFalse(self.p.metadata.get("mounted"))

    def test_the_mule_survives_a_save(self):
        import shutil
        import tempfile
        from engine.save_load import SaveManager
        mount.buy_mule(self.engine)
        tmp = tempfile.mkdtemp()
        try:
            sm = SaveManager(save_dir=tmp)
            sm.save(self.engine, name="mule")
            self.p.metadata.pop("mule", None)
            self.assertTrue(sm.load(self.engine, name="mule"))
            self.assertTrue(mount.has_mule(self.engine.player))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
