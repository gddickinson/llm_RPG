"""Tests for the quest board."""

import unittest

from engine.game_engine import GameEngine


class TestQuestBoard(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _move_to_tavern(self):
        for loc in self.engine.world.locations:
            if "Tavern" in loc.name:
                cx, cy = loc.center()
                self.engine.player.position = (cx, cy)
                return True
        return False

    def test_board_exists_at_tavern(self):
        ok = self._move_to_tavern()
        self.assertTrue(ok)
        board = self.engine.quest_board_at_player()
        self.assertIsNotNone(board)
        self.assertTrue(board.posted_quest_ids)

    def test_no_board_in_wilderness(self):
        self.engine.player.position = (0, 0)
        board = self.engine.quest_board_at_player()
        self.assertIsNone(board)

    def test_accept_from_board(self):
        self._move_to_tavern()
        board = self.engine.quest_board_at_player()
        qid = board.posted_quest_ids[0]
        ok = self.engine.accept_quest_from_board(qid)
        self.assertTrue(ok)
        from quests.quest import QuestStatus
        self.assertEqual(self.engine.quest_manager.get(qid).status,
                         QuestStatus.ACTIVE)

    def test_cannot_accept_off_board(self):
        # Not at tavern
        self.engine.player.position = (0, 0)
        ok = self.engine.accept_quest_from_board("herb_gathering")
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()
