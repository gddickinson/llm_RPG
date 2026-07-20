"""'The Hex of Wychwood' — a 3-act WITCH/CURSE adventure (George: rich, layered
adventures), the third authored purely as data over the reusable AdventureSeeder
and the first to lean on the shapeshift/curse system: a green hag hollows the
folk of a woodland hamlet into beasts. The finale over Mother Yall branches
Kill / Bind-and-free / Take-the-greenstaff."""

import os
import unittest

from engine.game_engine import GameEngine
from world.monsters import build_monster
from items.item_registry import create_item
from quests.quest_templates import create_quest


class TestWychwoodSeed(unittest.TestCase):
    def setUp(self):
        self._flag = os.environ.pop("LLM_RPG_NO_ADVENTURERS", None)
        self.addCleanup(os.environ.__setitem__,
                        "LLM_RPG_NO_ADVENTURERS", self._flag or "1")
        self.e = GameEngine(llm_provider="heuristic",
                            enable_npc_processes=False)
        self.e.start_game()
        self.w = self.e.wychwood

    def tearDown(self):
        try:
            self.e.end_game()
        except Exception:
            pass

    def test_areas_and_cast_seed(self):
        self.assertTrue(self.w.is_active())
        names = [a["name"] for a in self.w.areas]
        self.assertIn("Wychwood Hamlet", names)
        self.assertIn("The Hag's Hollow", names)
        for nid in ("granny_esk", "hedge_witch_odile", "cursed_lad_tam"):
            self.assertIsNotNone(self.e.npc_manager.get_npc(nid), nid)

    def test_hag_and_cursed_beasts_seed(self):
        cast = [n.name for n in self.e.npc_manager.npcs.values()]
        self.assertTrue(any("Mother Yall" in n for n in cast))

    def test_curse_token_clue_dropped(self):
        gi = self.e.world.ground_items or {}
        self.assertTrue(any(getattr(i, "id", "") == "curse_token"
                            for items in gi.values() for i in items))


class TestWychwoodContent(unittest.TestCase):
    def test_hag_drops_the_greenstaff(self):
        from items.loot_tables import generate_loot
        import random
        hag = build_monster("green_hag", (1, 1))
        self.assertGreaterEqual(hag.hp, 80)
        self.assertTrue(hag.goals)
        drops = generate_loot(hag, rng=random.Random(1))
        self.assertTrue(any(getattr(i, "id", "") == "crones_greenstaff"
                            for i in drops))

    def test_reward_items_exist_and_greenstaff_grants_a_shape(self):
        for iid in ("crones_greenstaff", "curse_token"):
            self.assertIsNotNone(create_item(iid), iid)
        staff = create_item("crones_greenstaff")
        # the hag's gift of shapes — a shapeshift use_effect (wolf)
        self.assertEqual(staff.use_effect.get("shapeshift", {}).get("form"),
                         "wolf")

    def test_quest_chain_chains_and_branches(self):
        q1 = create_quest("q_wychwood_vanishings")
        q2 = create_quest("q_wychwood_charm")
        q3 = create_quest("q_wychwood_reckoning")
        self.assertEqual(len(q1.objectives), 3)
        self.assertEqual(q2.metadata.get("prereq_quest"),
                         "q_wychwood_vanishings")
        self.assertEqual(q3.metadata.get("prereq_quest"), "q_wychwood_charm")
        self.assertEqual(len(q3.metadata.get("reward_choices", [])), 3)

    def test_seeded_hag_kill_completes_the_finale(self):
        from quests.quest import QuestStatus
        os.environ.pop("LLM_RPG_NO_ADVENTURERS", None)
        e = GameEngine(llm_provider="heuristic", enable_npc_processes=False)
        e.start_game()
        try:
            hag = next(n for n in e.npc_manager.npcs.values()
                       if "Mother Yall" in n.name)
            q3 = e.quest_manager.quests["q_wychwood_reckoning"]
            q3.status = QuestStatus.ACTIVE
            kls = getattr(getattr(hag, "character_class", None), "value", "")
            e.quest_manager.on_npc_defeated(hag.id, kls)
            self.assertTrue(q3.objectives[0].is_complete())
        finally:
            os.environ["LLM_RPG_NO_ADVENTURERS"] = "1"
            e.end_game()


if __name__ == "__main__":
    unittest.main()
