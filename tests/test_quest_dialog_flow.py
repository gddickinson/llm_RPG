"""Tests for the quest acceptance + turn-in flow via the engine API."""

import unittest

from engine.game_engine import GameEngine
from quests.quest import QuestStatus


class TestQuestDialogFlow(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_quests_start_available(self):
        # Per the new flow, quests should be offered (AVAILABLE), not active
        qm = self.engine.quest_manager
        self.assertIsNotNone(qm)
        self.assertGreater(len(qm.available()), 0)
        self.assertEqual(len(qm.active()), 0)

    def test_guard_offers_troll_hunt(self):
        offered = self.engine.quests_offered_by("guard_01")
        ids = [q.id for q in offered]
        self.assertIn("troll_hunt", ids)

    def test_accept_quest(self):
        ok = self.engine.accept_quest("troll_hunt")
        self.assertTrue(ok)
        q = self.engine.quest_manager.get("troll_hunt")
        self.assertEqual(q.status, QuestStatus.ACTIVE)

    def test_complete_and_turn_in(self):
        self.engine.accept_quest("troll_hunt")
        self.engine.quest_manager.on_npc_defeated("troll_brigand_01")
        ready = self.engine.quests_to_turn_in_with("guard_01")
        self.assertEqual(len(ready), 1)
        before_gold = self.engine.player.gold
        ok = self.engine.turn_in_quest("troll_hunt")
        self.assertTrue(ok)
        self.assertGreater(self.engine.player.gold, before_gold)
        # XP awarded
        self.assertGreater(
            (self.engine.player.metadata or {}).get("xp", 0), 0)


if __name__ == "__main__":
    unittest.main()
