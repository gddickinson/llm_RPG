"""Timed quests (P21.4) — a set-piece against the clock.

A quest with a `time_limit` starts a countdown on acceptance; each turn it
ticks down, and one that expires unfinished FAILS (the P21.1 status).
Beat the clock and the countdown is cleared."""

import os as _os
import tempfile as _tempfile
_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_tq_"))

import unittest

from engine.game_engine import GameEngine
from quests.quest import (Quest, QuestObjective, ObjectiveType, QuestStatus)
from quests.quest_templates import create_quest, QUEST_TEMPLATES


class _Base(unittest.TestCase):
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

    def _timed(self, qid="race", limit=3):
        q = Quest(id=qid, title="Race", description="",
                  objectives=[QuestObjective(ObjectiveType.KILL, "brigand")],
                  status=QuestStatus.AVAILABLE, reward_gold=10)
        q.metadata["time_limit"] = limit
        self.qm.quests[qid] = q
        return q


class TestCountdown(_Base):
    def test_accepting_starts_the_clock(self):
        self._timed(limit=5)
        self.qm.accept_quest("race")
        self.assertEqual(self.qm.time_left("race"), 5)

    def test_each_turn_runs_it_down(self):
        self._timed(limit=5)
        self.qm.accept_quest("race")
        self.qm.on_turn_advanced()
        self.qm.on_turn_advanced()
        self.assertEqual(self.qm.time_left("race"), 3)

    def test_expiry_fails_the_quest(self):
        self._timed(limit=2)
        self.qm.accept_quest("race")
        for _ in range(2):
            self.qm.on_turn_advanced()
        self.assertEqual(self.qm.get("race").status, QuestStatus.FAILED)

    def test_beating_the_clock_clears_the_countdown(self):
        q = self._timed(limit=5)
        self.qm.accept_quest("race")
        q.objectives[0].progress = 1          # done
        self.qm.on_turn_advanced()
        self.assertIsNone(self.qm.time_left("race"))
        self.assertNotEqual(self.qm.get("race").status, QuestStatus.FAILED)

    def test_an_untimed_quest_is_unaffected(self):
        q = Quest(id="calm", title="Calm", description="",
                  objectives=[QuestObjective(ObjectiveType.TALK, "x")],
                  status=QuestStatus.AVAILABLE)
        self.qm.quests["calm"] = q
        self.qm.accept_quest("calm")
        for _ in range(50):
            self.qm.on_turn_advanced()
        self.assertEqual(self.qm.get("calm").status, QuestStatus.ACTIVE)
        self.assertIsNone(self.qm.time_left("calm"))


class TestContent(_Base):
    def test_the_timed_bounty_is_authored(self):
        self.assertIn("timed_bounty", QUEST_TEMPLATES)
        q = create_quest("timed_bounty")
        self.assertEqual(q.metadata.get("time_limit"), 60)
        self.assertEqual(q.objectives[0].obj_type, ObjectiveType.KILL)


if __name__ == "__main__":
    unittest.main()
