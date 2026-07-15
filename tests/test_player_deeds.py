"""NPCs notice the player — deeds digest tests (P3.8)."""

import unittest

from engine.game_engine import GameEngine
from engine.player_deeds import (record_deed, recent_deeds, deeds_digest,
                                 prompt_block, heuristic_comment,
                                 MAX_DEEDS)
from items.item_registry import create_item
from characters import equipment as eq


class TestDeeds(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()
        self.player = self.engine.player

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_deed_ledger_caps(self):
        for i in range(20):
            record_deed(self.engine, f"did thing {i}")
        deeds = self.player.metadata["recent_deeds"]
        self.assertEqual(len(deeds), MAX_DEEDS)
        self.assertEqual(deeds[-1], "did thing 19")

    def test_player_kill_records_deed(self):
        from world.monsters import build_monster
        px, py = self.player.position
        wolf = build_monster("wolf", (px + 1, py))
        wolf.hp = 1
        self.engine.npc_manager.add_npc(wolf)
        for _ in range(40):
            self.engine.combat_system.player_attack(wolf.name)
            if not wolf.is_active():
                break
        self.assertTrue(any("slew Wolf" in d
                            for d in recent_deeds(self.engine)))

    def test_quest_turn_in_records_deed(self):
        from quests.quest import QuestStatus
        quest = self.engine.quest_manager.get("tavern_intro")
        quest.status = QuestStatus.COMPLETED
        self.engine.turn_in_quest(quest.id)
        self.assertTrue(any("A Friendly Welcome" in d
                            for d in recent_deeds(self.engine)))

    def test_digest_includes_gear_level_and_deeds(self):
        sword = create_item("longsword")
        self.player.inventory.append(sword)
        eq.equip(self.player, sword)
        record_deed(self.engine, "slew Gorkash")
        digest = " ".join(deeds_digest(self.engine))
        self.assertIn("Longsword", digest)
        self.assertIn(f"level {self.player.level}", digest)
        self.assertIn("slew Gorkash", digest)

    def test_pet_appears_in_digest(self):
        self.player.metadata["pets"] = ["mining"]
        self.player.metadata["active_pet"] = "mining"
        digest = " ".join(deeds_digest(self.engine))
        self.assertIn("pebble golem", digest)

    def test_prompt_block_wired_into_dialog_prompt(self):
        from engine.dialog_protocol import build_prompt
        record_deed(self.engine, "slew Gorkash")
        goren = self.engine.npc_manager.get_npc("tavernkeeper_01")
        prompt = build_prompt(self.engine, goren, "Evening!", [])
        self.assertIn("WHAT PEOPLE KNOW OF THE PLAYER", prompt)
        self.assertIn("slew Gorkash", prompt)

    def test_heuristic_comment_mentions_a_deed(self):
        record_deed(self.engine, "slew Gorkash")
        import random
        forced = random.Random()
        forced.random = lambda: 0.0  # always comment
        comment = heuristic_comment(self.engine, rng=forced)
        self.assertIn("slew Gorkash", comment)

    def test_no_deeds_no_comment(self):
        self.player.metadata["recent_deeds"] = []
        import random
        forced = random.Random()
        forced.random = lambda: 0.0
        self.assertEqual(heuristic_comment(self.engine, rng=forced), "")

    def test_deeds_persist_in_saves(self):
        import shutil
        import tempfile
        from engine.save_load import SaveManager
        record_deed(self.engine, "slew Gorkash")
        tmp = tempfile.mkdtemp()
        try:
            sm = SaveManager(save_dir=tmp)
            sm.save(self.engine, name="dd")
            self.player.metadata["recent_deeds"] = []
            self.assertTrue(sm.load(self.engine, name="dd"))
            self.assertIn("slew Gorkash", recent_deeds(self.engine))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
