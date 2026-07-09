"""End-to-end tests for the P4.2b handcrafted quests."""

import unittest

from engine.game_engine import GameEngine
from quests.quest import QuestStatus
from items.item_registry import create_item


class TestAuthoredQuests(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()
        self.player = self.engine.player
        self.qm = self.engine.quest_manager

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_thirteen_authored_quests_offered(self):
        authored = [qid for qid in self.qm.quests
                    if not qid.startswith("radiant_")]
        self.assertGreaterEqual(len(authored), 13)

    def test_caer_aldwyn_expedition(self):
        self.assertTrue(self.qm.accept_quest("caer_aldwyn"))
        self.qm.on_location_entered("Ruined Keep")
        quest = self.qm.get("caer_aldwyn")
        self.assertFalse(quest.is_complete(), "bandits still standing")
        self.qm.on_npc_defeated("enc_bandit_x1", "brigand")
        self.qm.on_npc_defeated("enc_bandit_x2", "brigand")
        self.assertEqual(quest.status, QuestStatus.COMPLETED)
        # Turn-in grants the warding amulet
        self.assertTrue(self.engine.turn_in_quest("caer_aldwyn"))
        ids = [getattr(i, "id", "") for i in self.player.inventory]
        self.assertIn("amulet_warding", ids)

    def test_the_fence_gated_behind_roads_and_rivers(self):
        self.assertFalse(self.qm.accept_quest("the_fence"))
        self.qm.get("roads_and_rivers").status = QuestStatus.TURNED_IN
        self.assertTrue(self.qm.accept_quest("the_fence"))

    def test_the_fence_delivery_flow(self):
        self.qm.get("roads_and_rivers").status = QuestStatus.TURNED_IN
        self.qm.accept_quest("the_fence")
        karim = self.engine.npc_manager.get_npc("guard_01")
        px, py = self.player.position
        karim.position = (px + 1, py)
        self.player.inventory.append(create_item("stolen_jewelry"))
        self.engine.dialog_system.player_to_npc(karim.id, "Evidence.")
        self.assertEqual(self.qm.get("the_fence").status,
                         QuestStatus.COMPLETED)

    def test_ballad_tours_all_three_taverns(self):
        self.qm.accept_quest("ballad_of_you")
        quest = self.qm.get("ballad_of_you")
        for npc_id in ("tavernkeeper_01", "hamlet_innkeeper_01"):
            self.qm.on_npc_talked(npc_id)
        self.assertFalse(quest.is_complete(), "one barkeep left")
        self.qm.on_npc_talked("camp_taverner_01")
        self.assertEqual(quest.status, QuestStatus.COMPLETED)
        self.assertTrue(self.engine.turn_in_quest("ballad_of_you"))
        ids = [getattr(i, "id", "") for i in self.player.inventory]
        self.assertIn("flute", ids)

    def test_ruined_keep_location_exists_in_world(self):
        names = [loc.name for loc in self.engine.world.locations]
        self.assertIn("Ruined Keep", names,
                      "history sim must plant the keep the quest visits")


if __name__ == "__main__":
    unittest.main()
