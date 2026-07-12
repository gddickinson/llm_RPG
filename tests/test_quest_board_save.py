"""Quest-board persistence (P0.1b): the radiant / DM notices posted to a
board at runtime survive a save/load, instead of reverting to defaults."""

import os as _os
import shutil
import tempfile as _tempfile
_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_lib_"))

import unittest

from engine.game_engine import GameEngine
from engine.save_load import SaveManager
from quests.quest_board import QuestBoardManager


class TestBoardRoundTrip(unittest.TestCase):
    def test_to_from_dict_carries_live_postings(self):
        mgr = QuestBoardManager(engine=None)
        board = mgr.boards[0]
        board.posted_quest_ids.append("a_new_notice")
        data = mgr.to_dict()
        fresh = QuestBoardManager(engine=None)
        fresh.from_dict(data)
        self.assertIn("a_new_notice",
                      fresh.boards[0].posted_quest_ids)

    def test_a_save_only_board_is_recreated(self):
        mgr = QuestBoardManager(engine=None)
        mgr.from_dict({"boards": {"Ghost Keep": ["haunt_quest"]}})
        names = {b.location_name for b in mgr.boards}
        self.assertIn("Ghost Keep", names)


class TestBoardSurvivesSaveLoad(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False)
        self.engine.start_game()
        self.tmp = _tempfile.mkdtemp()

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_a_posted_notice_survives_a_load(self):
        board = self.engine.quest_board_manager.board_at("Oakvale Tavern")
        self.assertIsNotNone(board)
        board.posted_quest_ids.append("a_radiant_notice")
        sm = SaveManager(save_dir=self.tmp)
        sm.save(self.engine, name="boards")
        # wipe the live boards back to defaults, then load
        self.engine.quest_board_manager = QuestBoardManager(self.engine)
        self.assertNotIn(
            "a_radiant_notice",
            self.engine.quest_board_manager.board_at(
                "Oakvale Tavern").posted_quest_ids)
        self.assertTrue(sm.load(self.engine, name="boards"))
        self.assertIn(
            "a_radiant_notice",
            self.engine.quest_board_manager.board_at(
                "Oakvale Tavern").posted_quest_ids,
            "the notice is back on the board after loading")


if __name__ == "__main__":
    unittest.main()
