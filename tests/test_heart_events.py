"""Heart event tests (P3.5)."""

import unittest
from unittest.mock import MagicMock

from engine.game_engine import GameEngine
from engine.heart_events import HEART_EVENTS


class TestHeartEvents(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()
        self.player = self.engine.player
        self.goren = self.engine.npc_manager.get_npc("tavernkeeper_01")
        self.hem = self.engine.heart_events

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_below_threshold_nothing_fires(self):
        self.assertIsNone(self.hem.pending_event(self.goren))
        self.assertIsNone(self.hem.maybe_trigger(self.goren))

    def test_crossing_threshold_fires_scene_and_perk(self):
        self.goren.modify_relationship(self.player.id, 35)
        inv_before = len(self.player.inventory)
        prose = self.hem.maybe_trigger(self.goren)
        self.assertIsNotNone(prose)
        self.assertIn("Karim", prose)  # heuristic mode uses the outline
        self.assertEqual(len(self.player.inventory), inv_before + 1)
        self.assertIn("goren_30", self.hem.seen())
        log = " ".join(str(e) for e in
                       self.engine.memory_manager.game_history[-5:])
        self.assertIn("A moment with Goren", log)

    def test_fires_once_only(self):
        self.goren.modify_relationship(self.player.id, 35)
        self.hem.maybe_trigger(self.goren)
        self.assertIsNone(self.hem.maybe_trigger(self.goren))

    def test_lowest_threshold_fires_first(self):
        self.goren.modify_relationship(self.player.id, 90)
        self.hem.maybe_trigger(self.goren)
        self.assertIn("goren_30", self.hem.seen())
        self.assertNotIn("goren_60", self.hem.seen())
        # Next conversation fires the 60 event
        gold_before = self.player.gold
        self.hem.maybe_trigger(self.goren)
        self.assertIn("goren_60", self.hem.seen())
        self.assertEqual(self.player.gold, gold_before + 40)

    def test_dialog_flow_triggers_event(self):
        px, py = self.player.position
        self.goren.position = (px + 1, py)
        self.goren.modify_relationship(self.player.id, 29)
        # The +2 friendly-chat bonus crosses 30 during this exchange
        self.engine.dialog_system.player_to_npc(self.goren.id, "Cheers!")
        self.assertIn("goren_30", self.hem.seen())

    def test_llm_renders_outline_without_new_facts(self):
        self.engine.llm_interface.provider_name = "anthropic"
        self.engine.llm_interface.generate_response = MagicMock(
            return_value="Goren pours two ales and toasts to good roads; "
                         "he tells you how Karim once carried him from "
                         "the smoke of a fire that nearly took the "
                         "tavern.")
        self.goren.modify_relationship(self.player.id, 35)
        prose = self.hem.maybe_trigger(self.goren)
        self.assertIn("Karim", prose)
        self.engine.llm_interface.generate_response.assert_called_once()

    def test_llm_junk_falls_back_to_outline(self):
        self.engine.llm_interface.provider_name = "anthropic"
        self.engine.llm_interface.generate_response = MagicMock(
            return_value="ok")
        self.goren.modify_relationship(self.player.id, 35)
        prose = self.hem.maybe_trigger(self.goren)
        self.assertIn("Karim", prose, "short junk must fall back")

    def test_npc_remembers_the_moment(self):
        self.goren.modify_relationship(self.player.id, 35)
        self.hem.maybe_trigger(self.goren)
        self.assertTrue(any("meaningful moment" in m.get("event", "")
                            for m in self.goren.memories))

    def test_seen_events_persist_in_saves(self):
        import shutil
        import tempfile
        from engine.save_load import SaveManager
        self.goren.modify_relationship(self.player.id, 35)
        self.hem.maybe_trigger(self.goren)
        tmp = tempfile.mkdtemp()
        try:
            sm = SaveManager(save_dir=tmp)
            sm.save(self.engine, name="h")
            self.player.metadata["heart_events"] = []
            self.assertTrue(sm.load(self.engine, name="h"))
            self.assertIn("goren_30",
                          self.engine.heart_events.seen())
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_all_data_events_have_valid_shape(self):
        for npc_id, events in HEART_EVENTS.items():
            for e in events:
                self.assertIn("id", e)
                self.assertIsInstance(e["threshold"], int)
                self.assertGreater(len(e["outline"]), 50)


if __name__ == "__main__":
    unittest.main()
