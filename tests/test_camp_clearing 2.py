"""P37.6c — encounter-source / camp-clearing quests: clearing a bandit camp
thins the bandit spawns in the wild (George)."""

import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
import tempfile
os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                      tempfile.mkdtemp(prefix="llmrpg_camp_"))

import json
import unittest


class TestData(unittest.TestCase):
    def test_bandit_camp_and_chief_exist(self):
        lairs = json.load(open("data/lairs.json"))
        self.assertIn("bandit_camp", lairs)
        camp = lairs["bandit_camp"]
        self.assertEqual(camp["suppresses"], {"bandit": 0.2})
        templates = {o["template"] for o in camp["occupants"]}
        self.assertIn("bandit_chief", templates)
        self.assertIn("bandit", templates)
        monsters = json.load(open("data/monsters.json"))
        self.assertIn("bandit_chief", monsters)
        # the chief never wanders the wild — it's camp-only
        self.assertEqual(monsters["bandit_chief"].get("encounter_weight", 0), 0)

    def test_clear_quest_exists(self):
        quests = json.load(open("data/quests.json"))
        self.assertIn("q_clear_bandit_camp", quests)
        q = quests["q_clear_bandit_camp"]
        obj = q["objectives"][0]
        self.assertEqual(obj["type"], "kill")
        self.assertEqual(obj["target"], "bandit_chief")


class TestSuppression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from engine.game_engine import GameEngine
        cls.engine = GameEngine(llm_provider="heuristic",
                                enable_npc_processes=False)
        cls.engine.start_game()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.engine.end_game()
        except Exception:
            pass

    def test_apply_suppression_thins_the_template(self):
        ls = self.engine.lairs
        ls.suppression = {}
        self.assertEqual(ls.spawn_multiplier("bandit"), 1.0)
        ls._apply_suppression({"name": "Bandit Camp",
                               "suppresses": {"bandit": 0.2}})
        self.assertAlmostEqual(ls.spawn_multiplier("bandit"), 0.2)
        # a second cleared source compounds
        ls._apply_suppression({"name": "Another Camp",
                               "suppresses": {"bandit": 0.5}})
        self.assertAlmostEqual(ls.spawn_multiplier("bandit"), 0.1)
        ls.suppression = {}

    def test_encounter_table_weight_drops_after_clear(self):
        ls = self.engine.lairs
        ls.suppression = {}
        table = [("bandit", 2), ("wolf", 4), ("goblin", 2)]
        before = dict((t, w * ls.spawn_multiplier(t)) for t, w in table)
        ls._apply_suppression({"name": "Bandit Camp",
                               "suppresses": {"bandit": 0.2}})
        after = dict((t, w * ls.spawn_multiplier(t)) for t, w in table)
        self.assertLess(after["bandit"], before["bandit"])
        self.assertEqual(after["wolf"], before["wolf"])   # others untouched
        ls.suppression = {}

    def test_suppression_round_trips_save(self):
        ls = self.engine.lairs
        ls.suppression = {"bandit": 0.2}
        d = ls.to_dict()
        ls.suppression = {}
        ls.from_dict(d)
        self.assertAlmostEqual(ls.spawn_multiplier("bandit"), 0.2)
        ls.suppression = {}


class TestQuest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from engine.game_engine import GameEngine
        cls.engine = GameEngine(llm_provider="heuristic",
                                enable_npc_processes=False)
        cls.engine.start_game()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.engine.end_game()
        except Exception:
            pass

    def test_quest_offered_at_start(self):
        self.assertIn("q_clear_bandit_camp",
                      self.engine.quest_manager.quests)

    def test_killing_the_chief_completes_the_objective(self):
        qm = self.engine.quest_manager
        qm.accept_quest("q_clear_bandit_camp")
        q = qm.quests["q_clear_bandit_camp"]
        obj = q.objectives[0]
        self.assertFalse(obj.is_complete())
        # a slain bandit_chief (id encodes the template) advances the kill
        qm.on_npc_defeated("enc_bandit_chief_ab12cd", "brigand")
        self.assertTrue(obj.is_complete(),
                        "defeating the chief should complete the quest")


if __name__ == "__main__":
    unittest.main()
