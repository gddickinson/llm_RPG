"""Quest chains, capability unlocks, player delivery (P4.2 part 1)."""

import unittest

from engine.game_engine import GameEngine
from quests.quest import QuestStatus
from items.item_registry import create_item


class TestQuestCapabilities(unittest.TestCase):
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

    def test_all_authored_quests_offered_at_start(self):
        for qid in ("the_silver_edge", "roads_and_rivers",
                    "supply_run", "the_healers_art"):
            self.assertIn(qid, self.qm.quests)

    def test_prereq_hides_quest_until_done(self):
        healers = self.qm.get("the_healers_art")
        self.assertFalse(self.qm.is_unlocked(healers))
        self.assertFalse(self.qm.accept_quest("the_healers_art"))
        offered = [q.id for q in self.qm.offered_by("hamlet_priest_01")]
        self.assertNotIn("the_healers_art", offered)
        # Complete the prereq
        self.qm.get("herb_gathering").status = QuestStatus.TURNED_IN
        self.assertTrue(self.qm.is_unlocked(healers))
        self.assertTrue(self.qm.accept_quest("the_healers_art"))

    def test_spell_unlock_on_turn_in(self):
        self.qm.get("herb_gathering").status = QuestStatus.TURNED_IN
        self.qm.accept_quest("the_healers_art")
        self.player.inventory.append(create_item("potion"))
        self.qm.on_item_acquired("potion")
        self.assertTrue(self.engine.turn_in_quest("the_healers_art"))
        self.assertIn("heal", self.player.metadata.get(
            "spells_known", []))

    def test_teleport_unlock_on_turn_in(self):
        self.qm.accept_quest("roads_and_rivers")
        self.qm.on_location_entered("Riverside Hamlet")
        self.qm.on_location_entered("Stonepine Camp")
        self.assertTrue(self.engine.turn_in_quest("roads_and_rivers"))
        dests = {d["key"]: d for d in
                 self.engine.travel_system.destinations()}
        self.assertTrue(dests["riverside"]["unlocked"])
        self.assertTrue(dests["stonepine"]["unlocked"])

    def test_crafting_counts_for_fetch_objectives(self):
        self.qm.accept_quest("the_silver_edge")
        # Craft the blade at a forge with the ingredients
        self.player.gold = 200
        self.player.inventory += [create_item("sword"),
                                  create_item("troll_tooth"),
                                  create_item("stolen_jewelry")]
        from items.crafting import craft
        msg = craft(self.player, "silver_blade", {"forge": True})
        self.assertIn("craft", msg.lower())
        # The engine.craft wrapper fires the hook; simulate it
        self.qm.on_item_acquired("silver_blade")
        self.assertEqual(self.qm.get("the_silver_edge").status,
                         QuestStatus.COMPLETED)

    def test_player_delivery_by_talking(self):
        self.qm.accept_quest("supply_run")
        hilde = self.engine.npc_manager.get_npc("camp_smith_01")
        px, py = self.player.position
        hilde.position = (px + 1, py)
        self.player.inventory.append(create_item("iron_bar"))

        self.engine.dialog_system.player_to_npc(hilde.id, "For you.")
        quest = self.qm.get("supply_run")
        self.assertEqual(quest.status, QuestStatus.COMPLETED)
        ids = [getattr(i, "id", "") for i in self.player.inventory]
        self.assertNotIn("iron_bar", ids, "delivered item consumed")
        # scan the FULL history, not a tail window — ambient beats (a tower
        # alarm, an NPC greeting) can flood the last few events in a full run
        log = " ".join(str(e) for e in
                       self.engine.memory_manager.game_history)
        self.assertIn("hand over", log)

    def test_legacy_deliver_sword_quest_now_completable(self):
        """The shipped deliver_sword quest was uncompletable by the
        player before try_deliver existed."""
        self.qm.accept_quest("deliver_sword")
        karim = self.engine.npc_manager.get_npc("guard_01")
        px, py = self.player.position
        karim.position = (px + 1, py)
        self.player.inventory.append(create_item("sword"))
        self.engine.dialog_system.player_to_npc(karim.id, "A delivery.")
        self.assertEqual(self.qm.get("deliver_sword").status,
                         QuestStatus.COMPLETED)

    def test_topic_unlock_on_turn_in(self):
        self.qm.accept_quest("supply_run")
        self.qm.get("supply_run").objectives[0].increment(1)
        self.qm.get("supply_run").update_status()
        self.assertTrue(self.engine.turn_in_quest("supply_run"))
        self.assertIn("east_shaft",
                      self.player.metadata.get("topics_known", []))

    def test_unlocks_persist_in_saves(self):
        import shutil
        import tempfile
        from engine.save_load import SaveManager
        self.player.metadata.setdefault(
            "teleport_unlocks", []).append("riverside")
        tmp = tempfile.mkdtemp()
        try:
            sm = SaveManager(save_dir=tmp)
            sm.save(self.engine, name="u")
            self.player.metadata["teleport_unlocks"] = []
            self.assertTrue(sm.load(self.engine, name="u"))
            dests = {d["key"]: d for d in
                     self.engine.travel_system.destinations()}
            self.assertTrue(dests["riverside"]["unlocked"])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
