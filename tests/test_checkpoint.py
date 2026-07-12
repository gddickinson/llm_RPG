"""Soulslike death recovery (user-directed): a fatal fall drops a
bloodstain with your pack/coin/XP and wakes you at sanctuary; walk back
to reclaim it. No more hard game-over."""

import os as _os
import tempfile as _tempfile
_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_lib_"))

import unittest

from engine import checkpoint
from engine.game_engine import GameEngine
from items.item_registry import create_item


class TestCheckpoint(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False)
        self.engine.start_game()
        self.p = self.engine.player
        # a pack, some coin, some hard-won XP at level 3
        self.p.inventory = [create_item("bread"), create_item("bread"),
                            create_item("ale")]
        self.p.gold = 120
        self.p.level = 3
        from engine.leveling import xp_threshold
        self.floor = xp_threshold(3)
        self.p.metadata["xp"] = self.floor + 400

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _fall(self):
        self.site = tuple(self.p.position)
        return checkpoint.fall_and_recover(self.engine, None)

    def test_a_fall_drops_the_pack_as_a_bloodstain(self):
        gold0, n0 = self.p.gold, len(self.p.inventory)
        self._fall()
        self.assertEqual(self.p.gold, 0, "carried coin dropped")
        self.assertEqual(len(self.p.inventory), 0, "the pack dropped")
        bs = self.p.metadata.get("bloodstain")
        self.assertIsNotNone(bs)
        self.assertEqual(bs["gold"], gold0)
        self.assertEqual(len(bs["items"]), n0)
        self.assertEqual(tuple(bs["pos"]), self.site)

    def test_a_fall_wakes_you_alive_at_sanctuary(self):
        self._fall()
        self.assertGreater(self.p.hp, 0, "you live")
        self.assertNotEqual(tuple(self.p.position), self.site,
                            "you wake elsewhere, not on your corpse")

    def test_the_xp_hit_never_de_levels_you(self):
        xp0 = self.p.metadata["xp"]
        self._fall()
        self.assertLess(self.p.metadata["xp"], xp0, "you lost progress")
        self.assertGreaterEqual(self.p.metadata["xp"], self.floor,
                                "but not a whole level")
        from engine.leveling import level_for_xp
        self.assertEqual(level_for_xp(self.p.metadata["xp"]), 3)

    def test_marker_is_on_the_ground(self):
        self._fall()
        items = self.engine.world.get_items_at(*self.site)
        self.assertIn(checkpoint.MARKER, items)

    def test_reclaim_restores_everything(self):
        gold0 = self.p.gold
        n0 = len(self.p.inventory)
        xp0 = self.p.metadata["xp"]
        self._fall()
        held_xp = self.p.metadata["bloodstain"]["xp"]
        # stand on the stain and reclaim
        self.p.position = self.site
        msg = checkpoint.reclaim_bloodstain(self.engine)
        self.assertIsNotNone(msg)
        self.assertEqual(self.p.gold, gold0)
        self.assertEqual(len(self.p.inventory), n0)
        self.assertEqual(self.p.metadata["xp"], xp0,
                         "the lost XP comes back with the corpse")
        self.assertIsNone(self.p.metadata.get("bloodstain"))
        self.assertGreater(held_xp, 0)

    def test_reclaim_only_when_standing_on_it(self):
        self._fall()
        # somewhere that is NOT the stain
        self.p.position = (self.site[0] + 3, self.site[1] + 3)
        self.assertIsNone(checkpoint.reclaim_bloodstain(self.engine))
        self.assertTrue(checkpoint.has_bloodstain(self.engine),
                        "still out there until you walk back")

    def test_dying_again_overwrites_the_old_stain(self):
        self._fall()
        first = tuple(self.p.metadata["bloodstain"]["pos"])
        # earn a fresh pack, then fall again somewhere else
        self.p.inventory = [create_item("bread")]
        self.p.gold = 40
        self.p.position = (first[0] + 5, first[1])
        checkpoint.fall_and_recover(self.engine, None)
        bs = self.p.metadata["bloodstain"]
        self.assertNotEqual(tuple(bs["pos"]), first,
                            "the stain moved to the new fall")
        self.assertEqual(bs["gold"], 40, "old hoard is lost, this is new")

    def test_tick_auto_reclaims_on_the_spot(self):
        self._fall()
        self.p.position = self.site
        self.assertIsNotNone(checkpoint.tick(self.engine))
        self.assertFalse(checkpoint.has_bloodstain(self.engine))

    def test_no_hard_game_over_even_in_a_zone(self):
        from engine.defeat import handle_player_defeat
        import random
        # force the harshest roll; pretend we're in a zone
        self.engine.current_dungeon = object()
        try:
            survived, msg = handle_player_defeat(
                self.engine, None, rng=random.Random(0))
        finally:
            self.engine.current_dungeon = None
        self.assertTrue(survived, "death is never terminal now")
        self.assertTrue(checkpoint.has_bloodstain(self.engine))

    def test_bloodstain_survives_save_load(self):
        import shutil
        import tempfile
        from engine.save_load import SaveManager
        self._fall()
        pos = tuple(self.p.metadata["bloodstain"]["pos"])
        tmp = tempfile.mkdtemp()
        try:
            sm = SaveManager(save_dir=tmp)
            sm.save(self.engine, name="corpse")
            self.p.metadata["bloodstain"] = None
            self.assertTrue(sm.load(self.engine, name="corpse"))
            self.assertTrue(checkpoint.has_bloodstain(self.engine))
            self.assertEqual(tuple(self.engine.player.metadata
                                   ["bloodstain"]["pos"]), pos)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
