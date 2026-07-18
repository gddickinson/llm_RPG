"""The main arc — a spine, a climax, an ending (P21.2).

An authored main questline builds to the Elder Wyrm; slaying it and
turning in the finale wins the campaign, firing a once-only ending drawn
from the P20.5 chronicle."""

import os as _os
import tempfile as _tempfile
_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_camp_"))

import unittest

from engine.game_engine import GameEngine
from engine import campaign
from quests.quest_templates import QUEST_TEMPLATES, create_quest
from quests.quest import QuestStatus


def _recent(engine):
    return " ".join(e.get("text", "") if isinstance(e, dict) else str(e)
                    for e in engine.memory_manager.get_recent_history())


class TestArcData(unittest.TestCase):
    def test_the_arc_is_authored_and_chained(self):
        stages = ["main_1_the_stirring", "main_2_the_source",
                  "main_3_the_lore", "main_4_the_gathering_night",
                  "main_5_the_reckoning"]
        for i, qid in enumerate(stages):
            self.assertIn(qid, QUEST_TEMPLATES)
            q = create_quest(qid)
            self.assertTrue(q.metadata.get("main"), f"{qid} is a main quest")
            if i > 0:
                self.assertEqual(q.metadata.get("prereq_quest"),
                                 stages[i - 1], "chained to the prior stage")

    def test_the_finale_is_the_reckoning(self):
        fin = create_quest("main_5_the_reckoning")
        self.assertTrue(fin.metadata.get("main_finale"))
        self.assertEqual(fin.metadata.get("sets_flag"), "campaign_won")
        self.assertEqual(fin.objectives[0].target, "elder_dragon")


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


class TestSpine(_Base):
    def test_main_line_is_ordered(self):
        line = campaign.main_line(self.engine)
        self.assertEqual(line[0], "main_1_the_stirring")
        self.assertEqual(line[-1], "main_5_the_reckoning")

    def test_finale_id(self):
        self.assertEqual(campaign.finale_id(self.engine),
                         "main_5_the_reckoning")

    def test_main_quest_line_leads_then_pins(self):
        # T3.2: the HUD line points to the giver until accepted, then pins the
        # active main quest + its objective
        lead = campaign.main_quest_line(self.engine)
        self.assertIn("Alzara", lead, "a fresh game leads to the wizard")
        self.engine.accept_quest("main_1_the_stirring")
        pinned = campaign.main_quest_line(self.engine)
        self.assertIn("MAIN", pinned)
        self.assertIn("Stirring", pinned, "an accepted main quest is pinned")

    def test_slaying_the_wyrm_completes_the_finale(self):
        fin = create_quest("main_5_the_reckoning")
        fin.status = QuestStatus.ACTIVE
        self.qm.quests["main_5_the_reckoning"] = fin
        self.qm.on_npc_defeated("enc_elder_dragon_ff01", "monster")
        self.assertTrue(fin.is_complete(),
                        "a named quarry completes on its template's death")


class TestEnding(_Base):
    def _win(self):
        fin = create_quest("main_5_the_reckoning")
        fin.status = QuestStatus.ACTIVE
        self.qm.quests["main_5_the_reckoning"] = fin
        self.qm.on_npc_defeated("enc_elder_dragon_ff01", "monster")
        self.qm.turn_in("main_5_the_reckoning", self.engine.player)

    def test_turn_in_wins_the_campaign(self):
        self.assertFalse(campaign.is_won(self.engine))
        self._win()
        self.assertTrue(campaign.is_won(self.engine))

    def test_the_ending_fires_once(self):
        self._win()
        self.assertTrue(campaign.check_finale(self.engine))
        self.assertIn("shadow over the realm is lifted", _recent(self.engine))
        self.assertFalse(campaign.check_finale(self.engine),
                         "the ending fires only once")

    def test_the_ending_reads_the_chronicle(self):
        self.engine.chronicle.record("[Legend] A rival falls at last.")
        self._win()
        s = campaign.summary(self.engine)
        self.assertTrue(any("SHADOW LIFTS" in ln for ln in s))
        self.assertTrue(any("rival falls" in ln for ln in s),
                        "the saga you wrote closes the age")


if __name__ == "__main__":
    unittest.main()
