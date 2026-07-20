"""'The Hollowing of Ravenmoor' — a complex 3-act undead-mystery adventure
(George: rich, multi-objective, layered adventures). Seeds its own areas +
cast, a 3-act quest chain with a branching Destroy/Lay-to-Rest/Claim finale,
new undead, and the grave-crown relic."""

import os
import unittest

from engine.game_engine import GameEngine
from world.monsters import build_monster
from items.item_registry import create_item
from quests.quest_templates import create_quest


class TestRavenmoorSeed(unittest.TestCase):
    def setUp(self):
        # the suite gates adventure seeding off; enable it for this test
        self._flag = os.environ.pop("LLM_RPG_NO_ADVENTURERS", None)
        self.addCleanup(os.environ.__setitem__,
                        "LLM_RPG_NO_ADVENTURERS", self._flag or "1")
        self.e = GameEngine(llm_provider="heuristic",
                            enable_npc_processes=False)
        self.e.start_game()
        self.rm = self.e.ravenmoor

    def tearDown(self):
        try:
            self.e.end_game()
        except Exception:
            pass

    def test_areas_and_cast_seed(self):
        self.assertTrue(self.rm.is_active())
        names = [a["name"] for a in self.rm.areas]
        self.assertIn("Ravenmoor", names)
        self.assertIn("The Sunken Barrow", names)
        for nid in ("elder_maeve", "sister_alenn"):
            self.assertIsNotNone(self.e.npc_manager.get_npc(nid), nid)

    def test_boss_and_guards_seed(self):
        cast = [n.name for n in self.e.npc_manager.npcs.values()]
        self.assertTrue(any("Barrow-Wight" in n for n in cast))
        self.assertTrue(any("Grave-Warden" in n for n in cast))

    def test_journal_clue_dropped(self):
        gi = self.e.world.ground_items or {}
        self.assertTrue(any("Journal" in str(i)
                            for items in gi.values() for i in items))

    def test_persists_and_stays_seeded_once(self):
        d = self.rm.to_dict()
        self.assertEqual(self.rm.seed(), 0)   # idempotent
        rm2 = type(self.rm)(self.e)
        rm2.from_dict(d)
        self.assertTrue(rm2.is_active())


class TestRavenmoorContent(unittest.TestCase):
    def test_new_undead_have_traits(self):
        from engine import undead
        for mid in ("hollow_thrall", "grave_warden", "aedelric_wight"):
            m = build_monster(mid, (1, 1))
            self.assertTrue(undead.is_undead(m), mid)
            self.assertTrue(m.goals)

    def test_boss_drops_the_grave_crown(self):
        from items.loot_tables import generate_loot
        import random
        boss = build_monster("aedelric_wight", (1, 1))
        drops = generate_loot(boss, rng=random.Random(1))
        self.assertTrue(any(getattr(i, "id", "") == "grave_crown"
                            for i in drops))

    def test_quest_chain_loads_and_chains(self):
        q1 = create_quest("q_ravenmoor_hollow")
        q2 = create_quest("q_ravenmoor_barrow")
        q3 = create_quest("q_ravenmoor_reckoning")
        self.assertEqual(len(q1.objectives), 3)
        # the acts chain by prereq (the real gating mechanism)
        self.assertEqual(q2.metadata.get("prereq_quest"), "q_ravenmoor_hollow")
        self.assertEqual(q3.metadata.get("prereq_quest"), "q_ravenmoor_barrow")
        # the finale branches three ways
        self.assertEqual(len(q3.metadata.get("reward_choices", [])), 3)


if __name__ == "__main__":
    unittest.main()
