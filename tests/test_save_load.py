"""Tests for the save/load system."""

import os
import shutil
import tempfile
import unittest

from engine.game_engine import GameEngine
from engine.save_load import SaveManager


class TestSaveLoad(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.sm = SaveManager(save_dir=self.tmp)
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_save_creates_file(self):
        path = self.sm.save(self.engine, name="t1")
        self.assertTrue(os.path.exists(path))
        self.assertTrue(path.endswith("t1.json"))

    def test_roundtrip(self):
        # Mutate state
        self.engine.move_player(1, 0)
        self.engine.move_player(0, 1)
        before = (self.engine.player.position,
                  self.engine.turn_counter,
                  len(self.engine.player.inventory))

        self.sm.save(self.engine, name="t2")

        # Wreck state
        self.engine.player.position = (0, 0)
        self.engine.turn_counter = 0

        ok = self.sm.load(self.engine, name="t2")
        self.assertTrue(ok)
        self.assertEqual(self.engine.player.position, before[0])
        self.assertEqual(self.engine.turn_counter, before[1])
        self.assertEqual(len(self.engine.player.inventory), before[2])

    def test_list_saves(self):
        self.sm.save(self.engine, name="t3", label="manual")
        saves = self.sm.list_saves()
        self.assertEqual(len(saves), 1)
        self.assertEqual(saves[0]["label"], "manual")

    def test_quest_state_persists(self):
        if not self.engine.quest_manager:
            self.skipTest("quest manager disabled")
        self.engine.quest_manager.on_npc_defeated("troll_brigand_01")
        self.sm.save(self.engine, name="t4")
        # Reset quest state
        self.engine.quest_manager.quests = {}
        self.assertTrue(self.sm.load(self.engine, name="t4"))
        q = self.engine.quest_manager.get("troll_hunt")
        self.assertIsNotNone(q)


if __name__ == "__main__":
    unittest.main()
