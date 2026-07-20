"""Branching quests (P21.1) — choices, exclusions, the FAILED state.

Accepting one path fails its rivals; choice-flags open and shut later
paths; a quest can offer a choice of reward; and the long-dormant FAILED
status is finally wired. Demonstrated in content by the castle fork —
expose Duke Voss or take his offer."""

import os as _os
import tempfile as _tempfile
_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_qb_"))

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
        self.player = self.engine.player

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _q(self, qid, **meta):
        q = Quest(id=qid, title=qid.replace("_", " ").title(), description="",
                  objectives=[QuestObjective(ObjectiveType.TALK, "x")],
                  status=QuestStatus.AVAILABLE, reward_gold=50)
        q.metadata.update(meta)
        self.qm.quests[qid] = q
        return q

    def _complete(self, qid):
        self.qm.quests[qid].objectives[0].progress = 1


class TestExclusion(_Base):
    def test_accepting_one_path_fails_its_rival(self):
        self._q("side", excludes=["expose"])
        self._q("expose")
        self.qm.accept_quest("side")
        self.assertEqual(self.qm.get("expose").status, QuestStatus.FAILED)

    def test_a_rival_taken_locks_this_one_out(self):
        self._q("side")
        e = self._q("expose", excluded_by=["side"])
        self.qm.accept_quest("side")
        self.assertFalse(self.qm.is_unlocked(e))

    def test_fail_is_idempotent(self):
        self._q("doomed")
        self.assertTrue(self.qm.fail_quest("doomed"))
        self.assertFalse(self.qm.fail_quest("doomed"), "already failed")


class TestFlags(_Base):
    def test_turn_in_sets_the_choice_flag(self):
        self._q("choose", sets_flag="chose_a")
        self.qm.accept_quest("choose")
        self._complete("choose")
        self.qm.turn_in("choose", self.player)
        self.assertTrue(self.player.metadata["quest_flags"].get("chose_a"))

    def test_prereq_flag_gates_a_path(self):
        gated = self._q("aftermath", prereq_flag="chose_a")
        self.assertFalse(self.qm.is_unlocked(gated))
        self.player.metadata.setdefault("quest_flags", {})["chose_a"] = True
        self.assertTrue(self.qm.is_unlocked(gated))

    def test_blocked_by_flag_shuts_a_path(self):
        loyal = self._q("loyalist", blocked_by_flag="chose_a")
        self.assertTrue(self.qm.is_unlocked(loyal))
        self.player.metadata.setdefault("quest_flags", {})["chose_a"] = True
        self.assertFalse(self.qm.is_unlocked(loyal))


class TestRewardChoice(_Base):
    def test_choosing_a_reward_pays_that_option(self):
        self._q("bounty", reward_choices=[
            {"gold": 10, "label": "coin"},
            {"gold": 0, "xp": 200, "label": "training"}])
        self.qm.accept_quest("bounty")
        self.assertTrue(self.qm.choose_reward("bounty", 1))
        self._complete("bounty")
        g0 = self.player.gold
        self.qm.turn_in("bounty", self.player)
        self.assertEqual(self.player.gold, g0, "picked training, not coin")

    def test_default_reward_is_the_first_option(self):
        self._q("bounty", reward_choices=[
            {"gold": 30, "label": "coin"}, {"gold": 0, "label": "nothing"}])
        self.qm.accept_quest("bounty")
        self._complete("bounty")
        g0 = self.player.gold
        self.qm.turn_in("bounty", self.player)
        self.assertEqual(self.player.gold, g0 + 30)

    def test_finale_legend_reaches_the_player_log(self):
        # the authored branching-finale ending must be SEEN — it was only going
        # to the quest manager's private event_log, never the player's log or
        # the chronicle (George: dead finale content across every adventure)
        self._q("finale", reward_choices=[
            {"gold": 0, "label": "slay",
             "legend": "You end the wyrm and the mountain is free."},
            {"gold": 0, "label": "spare", "legend": "You let it fly north."}])
        self.qm.accept_quest("finale")
        self.qm.choose_reward("finale", 0)
        self._complete("finale")
        self.qm.turn_in("finale", self.player)
        events = [h["event"] for h in
                  self.engine.memory_manager.game_history]
        self.assertTrue(
            any("[Legend]" in e and "end the wyrm" in e for e in events),
            "the chosen finale legend must reach the player's event log")


class TestCastleFork(_Base):
    def test_the_voss_offer_exists_and_forks(self):
        self.assertIn("castle_voss_gambit", QUEST_TEMPLATES)
        voss = create_quest("castle_voss_gambit")
        self.assertIn("castle_gambit", voss.metadata.get("excludes", []))
        self.assertEqual(voss.metadata.get("sets_flag"), "sided_with_voss")

    def test_the_two_paths_are_mutually_exclusive(self):
        # both become live, then siding with the Duke fails exposing him
        for qid in ("castle_gambit", "castle_voss_gambit"):
            q = create_quest(qid)
            q.metadata.pop("prereq_quest", None)   # test the fork, not the gate
            q.status = QuestStatus.AVAILABLE
            self.qm.quests[qid] = q
        self.qm.accept_quest("castle_voss_gambit")
        self.assertEqual(self.qm.get("castle_gambit").status,
                         QuestStatus.FAILED,
                         "you cannot both side with Voss and expose him")


if __name__ == "__main__":
    unittest.main()
