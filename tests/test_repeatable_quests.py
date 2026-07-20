"""T4.5 repeatable + branching quests: a standing task re-arms after
turn-in; an excludes-fork shuts the door on its rival."""

import unittest

from engine.game_engine import GameEngine
from quests.quest_templates import create_quest, QUEST_TEMPLATES
from quests.quest import QuestStatus


class TestNewQuestsLoad(unittest.TestCase):
    def test_new_quests_registered(self):
        for qid in ("bounty_wolves", "standing_herbs", "cull_goblins",
                    "the_bandit_bargain", "bring_brigand_to_justice"):
            self.assertIn(qid, QUEST_TEMPLATES)
            self.assertIsNotNone(create_quest(qid))

    def test_repeatable_flag_reaches_metadata(self):
        q = create_quest("bounty_wolves")
        self.assertTrue(q.metadata.get("repeatable"))


class TestRepeatable(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False)
        self.engine.start_game()
        self.qm = self.engine.quest_manager

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _seed(self, qid):
        q = create_quest(qid)
        self.qm.quests[qid] = q
        return q

    def test_repeatable_rearms_after_turn_in(self):
        q = self._seed("bounty_wolves")
        self.assertTrue(self.qm.accept_quest("bounty_wolves"))
        # complete the objective
        for obj in q.objectives:
            obj.progress = obj.required
        q.update_status()
        self.assertEqual(q.status, QuestStatus.COMPLETED)
        self.assertTrue(self.qm.turn_in("bounty_wolves", self.engine.player))
        # a repeatable quest is AVAILABLE again, objectives reset, tally up
        self.assertEqual(q.status, QuestStatus.AVAILABLE)
        self.assertEqual(q.objectives[0].progress, 0)
        self.assertEqual(q.metadata.get("times_done"), 1)
        # and it can be taken up + turned in a second time
        self.assertTrue(self.qm.accept_quest("bounty_wolves"))
        for obj in q.objectives:
            obj.progress = obj.required
        q.update_status()
        self.assertTrue(self.qm.turn_in("bounty_wolves", self.engine.player))
        self.assertEqual(q.metadata.get("times_done"), 2)

    def test_non_repeatable_stays_turned_in(self):
        q = self._seed("troll_hunt")
        self.qm.accept_quest("troll_hunt")
        for obj in q.objectives:
            obj.progress = obj.required
        q.update_status()
        self.qm.turn_in("troll_hunt", self.engine.player)
        self.assertEqual(q.status, QuestStatus.TURNED_IN)

    def test_excludes_fork_fails_the_rival(self):
        a = self._seed("the_bandit_bargain")
        b = self._seed("bring_brigand_to_justice")
        self.assertTrue(self.qm.accept_quest("the_bandit_bargain"))
        # accepting one path fails its rival (P21.1 machinery)
        self.assertEqual(b.status, QuestStatus.FAILED)
        self.assertEqual(a.status, QuestStatus.ACTIVE)


if __name__ == "__main__":
    unittest.main()
