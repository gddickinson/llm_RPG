"""'The Wyrm of Emberfell' — a complex 3-act dragon adventure (George: rich,
multi-objective, layered adventures), authored via the REUSABLE data-driven
`engine.adventure_seed.AdventureSeeder`: a mountain village raided by a wyrm's
brood, a scholar who knows its weakness, and a branching Slay / Drive-off /
Bargain finale over the named boss Cindermaw."""

import os
import unittest

from engine.game_engine import GameEngine
from world.monsters import build_monster
from items.item_registry import create_item
from quests.quest_templates import create_quest


class TestEmberfellSeed(unittest.TestCase):
    def setUp(self):
        # the suite gates adventure seeding off; enable it for this test
        self._flag = os.environ.pop("LLM_RPG_NO_ADVENTURERS", None)
        self.addCleanup(os.environ.__setitem__,
                        "LLM_RPG_NO_ADVENTURERS", self._flag or "1")
        self.e = GameEngine(llm_provider="heuristic",
                            enable_npc_processes=False)
        self.e.start_game()
        self.emb = self.e.emberfell

    def tearDown(self):
        try:
            self.e.end_game()
        except Exception:
            pass

    def test_areas_and_cast_seed(self):
        self.assertTrue(self.emb.is_active())
        names = [a["name"] for a in self.emb.areas]
        self.assertIn("Emberfell Village", names)
        self.assertIn("The Wyrm's Roost", names)
        for nid in ("reeve_halden", "loremaster_yorwin", "shepherd_bryn"):
            self.assertIsNotNone(self.e.npc_manager.get_npc(nid), nid)

    def test_boss_and_brood_seed(self):
        cast = [n.name for n in self.e.npc_manager.npcs.values()]
        self.assertTrue(any("Cindermaw" in n for n in cast))
        self.assertTrue(any("Whelp" in n for n in cast))

    def test_scale_clue_dropped(self):
        gi = self.e.world.ground_items or {}
        self.assertTrue(any(getattr(i, "id", "") == "scorched_scale"
                            for items in gi.values() for i in items))

    def test_persists_and_stays_seeded_once(self):
        from engine.adventure_seed import AdventureSeeder
        d = self.emb.to_dict()
        self.assertEqual(self.emb.seed(), 0)   # idempotent
        emb2 = AdventureSeeder(self.e, "emberfell.json")
        emb2.from_dict(d)
        self.assertTrue(emb2.is_active())
        self.assertEqual(emb2.area_pos("wyrms_roost"),
                         self.emb.area_pos("wyrms_roost"))


class TestEmberfellContent(unittest.TestCase):
    def test_boss_has_a_breath_telegraph_and_drops_emberfang(self):
        from items.loot_tables import generate_loot
        import random
        wyrm = build_monster("emberfell_wyrm", (1, 1))
        self.assertGreaterEqual(wyrm.hp, 120)
        self.assertTrue(wyrm.goals)
        boss = (wyrm.metadata.get("behavior", {}) or {}).get("boss") \
            or (wyrm.metadata.get("boss"))
        # the telegraph rides through build_monster onto behavior/metadata
        self.assertTrue(
            any("breath" in str(v) for v in wyrm.metadata.values())
            or boss, "the wyrm should carry its breath telegraph")
        drops = generate_loot(wyrm, rng=random.Random(1))
        self.assertTrue(any(getattr(i, "id", "") == "emberfang_spear"
                            for i in drops))

    def test_reward_items_exist(self):
        for iid in ("emberfang_spear", "scorched_scale", "wyrmsbane_draught"):
            self.assertIsNotNone(create_item(iid), iid)

    def test_quest_chain_loads_and_chains(self):
        q1 = create_quest("q_emberfell_raids")
        q2 = create_quest("q_emberfell_weakness")
        q3 = create_quest("q_emberfell_reckoning")
        self.assertEqual(len(q1.objectives), 3)
        self.assertEqual(q2.metadata.get("prereq_quest"), "q_emberfell_raids")
        self.assertEqual(q3.metadata.get("prereq_quest"),
                         "q_emberfell_weakness")
        # the finale branches three ways (slay / drive off / bargain)
        self.assertEqual(len(q3.metadata.get("reward_choices", [])), 3)

    def test_kill_objectives_match_the_seeded_monsters(self):
        # a KILL objective advances off the encounter-id TEMPLATE, so the
        # objective targets must equal the seeded monster template ids
        from engine.game_engine import GameEngine
        from quests.quest import QuestStatus
        os.environ.pop("LLM_RPG_NO_ADVENTURERS", None)
        e = GameEngine(llm_provider="heuristic", enable_npc_processes=False)
        e.start_game()
        try:
            qm = e.quest_manager
            q1 = qm.quests["q_emberfell_raids"]
            qm.accept_quest("q_emberfell_raids")
            whelp = next(o for o in q1.objectives if o.obj_type.value == "kill")
            qm.on_npc_defeated("enc_dragon_whelp_a1", "monster")
            self.assertTrue(whelp.is_complete(), "whelp kill advances Act 1")

            q3 = qm.quests["q_emberfell_reckoning"]
            q3.status = QuestStatus.ACTIVE
            qm.on_npc_defeated("enc_emberfell_wyrm_a1", "monster")
            self.assertTrue(q3.objectives[0].is_complete(),
                            "the wyrm kill completes the finale")
        finally:
            os.environ["LLM_RPG_NO_ADVENTURERS"] = "1"
            e.end_game()


class TestGenericSeederReusable(unittest.TestCase):
    """The seeder is data-driven — a new adventure is a JSON file, no code."""

    def test_npc_ids_of_reads_the_data_file(self):
        from engine.adventure_seed import npc_ids_of
        ids = npc_ids_of("emberfell.json")
        self.assertIn("reeve_halden", ids)
        self.assertIn("loremaster_yorwin", ids)

    def test_seed_is_gated_off_by_env(self):
        from engine.adventure_seed import AdventureSeeder
        os.environ["LLM_RPG_NO_ADVENTURERS"] = "1"
        try:
            e = GameEngine(llm_provider="heuristic",
                           enable_npc_processes=False)
            e.start_game()
            self.assertFalse(e.emberfell.is_active())
            e.end_game()
        finally:
            os.environ["LLM_RPG_NO_ADVENTURERS"] = "1"


if __name__ == "__main__":
    unittest.main()
