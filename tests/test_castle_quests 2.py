"""The castle adventure (P18.6): the court-intrigue quest chain and the
crypt threat, given by the Bloodstone cast."""

import os as _os
import tempfile as _tempfile
_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_lib_"))

import unittest

from engine.game_engine import GameEngine
from quests.quest import QuestStatus
from quests.quest_templates import QUEST_TEMPLATES, create_quest

CHAIN = ["castle_audience", "castle_whispers", "castle_the_spy",
         "castle_gambit", "castle_crypt"]


class TestQuestData(unittest.TestCase):
    def test_the_castle_chain_is_authored(self):
        for qid in CHAIN:
            self.assertIn(qid, QUEST_TEMPLATES, f"{qid} missing")

    def test_givers_are_the_castle_cast(self):
        from characters.npc_presets import NPC_SPECS
        for qid in CHAIN:
            giver = create_quest(qid).giver_id
            self.assertIn(giver, NPC_SPECS, f"{qid} giver {giver}")
            self.assertTrue(NPC_SPECS[giver].get("zone_bound"),
                            f"{qid} is given by a castle resident")

    def test_the_intrigue_targets_the_rival_and_the_crown(self):
        # the spy quest hunts the Duke's cipher; the gambit faces the King
        # and the Duke; the crypt quest lays the dead
        spy = [o.target for o in create_quest("castle_the_spy").objectives]
        self.assertTrue(any(t == "dukes_cipher" for t in spy))
        gambit = {o.target for o in
                  create_quest("castle_gambit").objectives}
        self.assertIn("duke_voss", gambit)
        crypt = create_quest("castle_crypt").objectives[0]
        self.assertEqual(crypt.obj_type.value, "kill")

    def test_the_cipher_waits_in_the_apartments(self):
        from world.structures import STRUCTURES
        apts = next(lv for lv in STRUCTURES["bloodstone_castle"]["levels"]
                    if "Royal Apartments" in lv["name"])
        self.assertIn("dukes_cipher", apts.get("chest_loot", []))


class TestChaining(unittest.TestCase):
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

    def test_audience_is_open_but_the_rest_wait_on_it(self):
        for qid in CHAIN:
            self.qm.offer_quest(qid)
        self.assertTrue(self.qm.is_unlocked(self.qm.quests["castle_audience"]),
                        "the first quest needs no prereq")
        self.assertFalse(
            self.qm.is_unlocked(self.qm.quests["castle_whispers"]),
            "whispers waits on the audience")

    def test_turning_in_the_audience_unlocks_the_whispers(self):
        for qid in ("castle_audience", "castle_whispers"):
            self.qm.offer_quest(qid)
        self.qm.quests["castle_audience"].status = QuestStatus.TURNED_IN
        self.assertTrue(
            self.qm.is_unlocked(self.qm.quests["castle_whispers"]))

    def test_a_talk_objective_completes_on_the_right_words(self):
        self.qm.offer_quest("castle_audience")
        self.assertTrue(self.qm.accept_quest("castle_audience"))
        self.qm.on_npc_talked("king_bloodstone")
        q = self.qm.quests["castle_audience"]
        self.assertTrue(q.objectives[0].is_complete(),
                        "being presented to the King completes it")

    def test_the_crypt_quest_counts_the_restless_dead(self):
        self.qm.offer_quest("castle_audience")
        self.qm.quests["castle_audience"].status = QuestStatus.TURNED_IN
        self.qm.offer_quest("castle_crypt")
        self.assertTrue(self.qm.accept_quest("castle_crypt"))
        for _ in range(3):
            self.qm.on_npc_defeated("some_bones", "monster")
        self.assertTrue(
            self.qm.quests["castle_crypt"].objectives[0].is_complete())


if __name__ == "__main__":
    unittest.main()
