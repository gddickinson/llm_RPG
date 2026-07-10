"""Nightly world director tests (P3.7)."""

import unittest
from unittest.mock import MagicMock

from engine.game_engine import GameEngine
from engine.director import SHORTAGE_MARKUP


class TestDirector(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()
        self.director = self.engine.world_director

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_heuristic_night_produces_events(self):
        notes = self.director.run_night()
        self.assertGreaterEqual(len(notes), 1)
        log = " ".join(str(e) for e in
                       self.engine.memory_manager.game_history[-5:])
        self.assertIn("[Overnight]", log)

    def test_shortage_raises_shop_prices(self):
        self.director._apply({"type": "shortage", "item_id": "ale"})
        self.assertEqual(self.director.shortage_multiplier("ale"),
                         SHORTAGE_MARKUP)
        goren = self.engine.npc_manager.get_npc("tavernkeeper_01")
        from items.item_registry import create_item
        ale = create_item("ale")
        surged = self.engine.shop_manager.buy_price(
            self.engine.player, ale, goren)
        self.director.shortages = {}
        normal = self.engine.shop_manager.buy_price(
            self.engine.player, ale, goren)
        self.assertGreater(surged, normal)

    def test_shortage_expires(self):
        self.director._apply({"type": "shortage", "item_id": "bread"})
        self.engine.world.time += 24 * 60 + 1
        self.assertEqual(self.director.shortage_multiplier("bread"), 1.0)

    def test_sighting_spawns_real_monster(self):
        before = len(self.engine.npc_manager.npcs)
        note = self.director._apply(
            {"type": "monster_sighting", "template": "wolf"})
        self.assertIn("Wolf", note)
        self.assertEqual(len(self.engine.npc_manager.npcs), before + 1)

    def test_feud_drops_mutual_relationship(self):
        note = self.director._apply({
            "type": "feud", "npc_a": "tavernkeeper_01",
            "npc_b": "blacksmith_01"})
        self.assertIn("falling-out", note)
        goren = self.engine.npc_manager.get_npc("tavernkeeper_01")
        self.assertEqual(goren.get_relationship("blacksmith_01"), -20)

    def test_invalid_ids_are_noops(self):
        self.assertEqual(self.director._apply(
            {"type": "shortage", "item_id": "unobtainium"}), "")
        self.assertEqual(self.director._apply(
            {"type": "monster_sighting", "template": "dragon"}), "")
        self.assertEqual(self.director._apply(
            {"type": "feud", "npc_a": "ghost", "npc_b": "phantom"}), "")

    def test_rumors_flow_into_gossip(self):
        self.director.rumors = ["The mill wheel broke overnight."]
        from characters.gossip import gossip_for
        # Isolate from competing gossip sources: an NPC with no family,
        # an empty event log, and no world history to cite
        goren = self.engine.npc_manager.get_npc("tavernkeeper_01")
        self.engine.memory_manager.game_history = []
        self.engine.world_history = []
        from characters import families
        original = families.family_of
        families.family_of = lambda nid: None
        try:
            found = False
            for _ in range(25):  # rumor slot hits at 60% per try
                lines = gossip_for(goren, self.engine, max_lines=1)
                if any("mill wheel" in ln for ln in lines):
                    found = True
                    break
            self.assertTrue(found,
                            "director rumor never surfaced in gossip")
        finally:
            families.family_of = original

    def test_llm_events_parsed_and_applied(self):
        self.engine.llm_interface.provider_name = "anthropic"
        self.engine.llm_interface.generate_response = MagicMock(
            return_value='[{"type": "rumor", "text": "The keep glows at '
                         'night."}, {"type": "shortage", '
                         '"item_id": "potion"}]')
        notes = self.director.run_night()
        self.assertEqual(len(notes), 2)
        self.assertIn("The keep glows at night.", self.director.rumors)
        self.assertGreater(
            self.director.shortage_multiplier("potion"), 1.0)

    def test_llm_junk_falls_back_to_heuristic(self):
        self.engine.llm_interface.provider_name = "anthropic"
        self.engine.llm_interface.generate_response = MagicMock(
            return_value="The night passes uneventfully.")
        notes = self.director.run_night()
        self.assertGreaterEqual(len(notes), 1,
                                "junk must fall back to heuristic events")

    def test_day_change_runs_director(self):
        now = self.engine.world.time
        self.engine.world.time = ((now // (24 * 60)) + 1) * 24 * 60
        self.engine.advance_turn()
        log = " ".join(str(e) for e in
                       self.engine.memory_manager.game_history[-8:])
        self.assertIn("[Overnight]", log)

    def test_state_persists_in_saves(self):
        import shutil
        import tempfile
        from engine.save_load import SaveManager
        self.director.rumors = ["A two-headed calf was born."]
        self.director._apply({"type": "shortage", "item_id": "ale"})
        tmp = tempfile.mkdtemp()
        try:
            sm = SaveManager(save_dir=tmp)
            sm.save(self.engine, name="d")
            self.director.rumors = []
            self.director.shortages = {}
            self.assertTrue(sm.load(self.engine, name="d"))
            self.assertIn("A two-headed calf was born.",
                          self.engine.world_director.rumors)
            self.assertGreater(
                self.engine.world_director.shortage_multiplier("ale"),
                1.0)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
