"""Audit fix (A-board): the tavern quest BOARD is now reachable.

`quest_board_manager` posted radiant + starter notices with no player
trigger — `quest_board_at_player()`/`accept_from_board()` had no caller, so
the board was stranded. Now standing at the tavern board, [E] opens a
numbered overlay to read and take posted work.
"""

import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
import tempfile
os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                      tempfile.mkdtemp(prefix="llmrpg_board_"))

import unittest

from quests.quest import QuestStatus


class TestQuestBoardReach(unittest.TestCase):
    def setUp(self):
        from engine.game_engine import GameEngine
        self.eng = GameEngine(llm_provider="heuristic",
                              enable_npc_processes=False)
        self.eng.start_game()
        # the board hangs INSIDE the tavern (PT3.1) — enter it
        self.tavern = next(
            (l for l in self.eng.world.locations
             if l.name == "Oakvale Tavern"), None)
        self.assertIsNotNone(self.tavern, "the tavern board's location exists")
        self.eng.player.position = (self.tavern.x, self.tavern.y)
        self.eng.enter_building(self.tavern)

    def tearDown(self):
        try:
            self.eng.end_game()
        except Exception:
            pass

    def test_board_detected_at_the_tavern(self):
        self.assertIsNotNone(self.eng.quest_board_at_player())

    def test_no_board_out_in_the_open(self):
        # leave the tavern and stand in open country — no board hangs there
        self.eng.current_interior = None
        self.eng.player.position = (1, 1)
        self.assertIsNone(self.eng.quest_board_at_player())

    def test_overlay_lists_posted_notices(self):
        lines = self.eng.board_overlay_lines()
        self.assertTrue(lines)
        joined = " ".join(lines).lower()
        self.assertIn("board", joined)
        # at least one numbered notice
        self.assertTrue(any(l.startswith("[1]") for l in lines),
                        f"expected a numbered notice, got {lines}")

    def test_accept_index_starts_the_quest(self):
        self.eng.board_overlay_lines()          # populate the listing
        qm = self.eng.quest_manager
        board = self.eng.quest_board_at_player()
        # find the first still-available posted quest
        avail = self.eng.quest_board_manager.list_available(board)
        self.assertTrue(avail, "the fresh board has available notices")
        first_id = avail[0].id
        msg = self.eng.board_accept_index(0)
        self.assertIn("notice", msg.lower())
        self.assertEqual(qm.get(first_id).status, QuestStatus.ACTIVE)

    def test_accept_out_of_range_is_safe(self):
        self.eng.board_overlay_lines()
        self.assertIn("no notice", self.eng.board_accept_index(8).lower())


if __name__ == "__main__":
    unittest.main()
