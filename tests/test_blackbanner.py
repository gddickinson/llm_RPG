"""'The Blackbanner Reaving' — a 3-act HUMAN-antagonist adventure (George: rich,
complex, layered adventures), the second one authored purely as data over the
reusable `engine.adventure_seed.AdventureSeeder`. An outlaw warlord unites the
raiding camps; the finale over Vharo Blackbanner branches Kill / Turn-the-
captains / Seize-the-banner."""

import os
import unittest

from engine.game_engine import GameEngine
from world.monsters import build_monster
from items.item_registry import create_item
from quests.quest_templates import create_quest


class TestBlackbannerSeed(unittest.TestCase):
    def setUp(self):
        self._flag = os.environ.pop("LLM_RPG_NO_ADVENTURERS", None)
        self.addCleanup(os.environ.__setitem__,
                        "LLM_RPG_NO_ADVENTURERS", self._flag or "1")
        self.e = GameEngine(llm_provider="heuristic",
                            enable_npc_processes=False)
        self.e.start_game()
        self.bb = self.e.blackbanner

    def tearDown(self):
        try:
            self.e.end_game()
        except Exception:
            pass

    def test_areas_and_cast_seed(self):
        self.assertTrue(self.bb.is_active())
        names = [a["name"] for a in self.bb.areas]
        self.assertIn("Redgate Waystation", names)
        self.assertIn("The Blackbanner Camp", names)
        for nid in ("marshal_orsa", "caravan_master_deel", "lieutenant_kessa"):
            self.assertIsNotNone(self.e.npc_manager.get_npc(nid), nid)

    def test_warlord_and_raiders_seed(self):
        cast = [n.name for n in self.e.npc_manager.npcs.values()]
        self.assertTrue(any("Vharo" in n for n in cast))

    def test_muster_clue_dropped(self):
        gi = self.e.world.ground_items or {}
        self.assertTrue(any(getattr(i, "id", "") == "blackbanner_muster"
                            for items in gi.values() for i in items))

    def test_swayable_lieutenant_is_not_hostile(self):
        kessa = self.e.npc_manager.get_npc("lieutenant_kessa")
        self.assertEqual(kessa.faction, "neutral")
        self.assertTrue(kessa.metadata.get("swayable"))


class TestBlackbannerContent(unittest.TestCase):
    def test_warlord_drops_the_black_banner(self):
        from items.loot_tables import generate_loot
        import random
        boss = build_monster("vharo_blackbanner", (1, 1))
        self.assertGreaterEqual(boss.hp, 80)
        self.assertTrue(boss.goals)
        drops = generate_loot(boss, rng=random.Random(1))
        self.assertTrue(any(getattr(i, "id", "") == "blackbanner_standard"
                            for i in drops))

    def test_reward_items_exist(self):
        for iid in ("blackbanner_standard", "blackbanner_muster"):
            self.assertIsNotNone(create_item(iid), iid)

    def test_quest_chain_chains_and_branches(self):
        q1 = create_quest("q_blackbanner_raids")
        q2 = create_quest("q_blackbanner_muster")
        q3 = create_quest("q_blackbanner_reckoning")
        self.assertEqual(len(q1.objectives), 3)
        self.assertEqual(q2.metadata.get("prereq_quest"), "q_blackbanner_raids")
        self.assertEqual(q3.metadata.get("prereq_quest"),
                         "q_blackbanner_muster")
        self.assertEqual(len(q3.metadata.get("reward_choices", [])), 3)

    def test_seeded_warlord_kill_completes_the_finale(self):
        from quests.quest import QuestStatus
        os.environ.pop("LLM_RPG_NO_ADVENTURERS", None)
        e = GameEngine(llm_provider="heuristic", enable_npc_processes=False)
        e.start_game()
        try:
            warlord = next(n for n in e.npc_manager.npcs.values()
                           if "Vharo" in n.name)
            q3 = e.quest_manager.quests["q_blackbanner_reckoning"]
            q3.status = QuestStatus.ACTIVE
            kls = getattr(getattr(warlord, "character_class", None),
                          "value", "")
            # the real defeat path: (id, class) — the id is enc_<template>_<hash>
            e.quest_manager.on_npc_defeated(warlord.id, kls)
            self.assertTrue(q3.objectives[0].is_complete())
        finally:
            os.environ["LLM_RPG_NO_ADVENTURERS"] = "1"
            e.end_game()

    def test_finale_turn_in_reshapes_the_world(self):
        # the finale disperses the guardian foes AND thins the theme's
        # wilderness encounters (George: finales reshape the world)
        from quests.quest import QuestStatus
        os.environ.pop("LLM_RPG_NO_ADVENTURERS", None)
        e = GameEngine(llm_provider="heuristic", enable_npc_processes=False)
        e.start_game()
        try:
            bb = e.blackbanner
            active0 = [nid for nid in bb.foe_ids
                       if e.npc_manager.npcs.get(nid)
                       and e.npc_manager.npcs[nid].is_active()]
            self.assertTrue(active0, "guardian foes are seeded")
            self.assertEqual(e.lairs.spawn_multiplier("bandit"), 1.0)
            # the boss falls (as the kill objective requires), then turn in
            warlord = next(n for n in e.npc_manager.npcs.values()
                           if "Vharo" in n.name)
            warlord.status = "defeated"
            e.world.map.remove_character(warlord)
            q3 = e.quest_manager.quests["q_blackbanner_reckoning"]
            q3.status = QuestStatus.ACTIVE
            for o in q3.objectives:
                o.progress = o.required
            q3.update_status()
            e.turn_in_quest("q_blackbanner_reckoning")
            self.assertTrue(bb.is_resolved())
            active1 = [nid for nid in bb.foe_ids
                       if e.npc_manager.npcs.get(nid)
                       and e.npc_manager.npcs[nid].is_active()]
            self.assertEqual(active1, [], "the guardian foes disperse")
            self.assertLess(e.lairs.spawn_multiplier("bandit"), 1.0,
                            "the confederation broken → fewer bandits")
            # the resolved state persists
            from engine.adventure_seed import AdventureSeeder
            bb2 = AdventureSeeder(e, "blackbanner.json")
            bb2.from_dict(bb.to_dict())
            self.assertTrue(bb2.is_resolved())
        finally:
            os.environ["LLM_RPG_NO_ADVENTURERS"] = "1"
            e.end_game()


if __name__ == "__main__":
    unittest.main()
