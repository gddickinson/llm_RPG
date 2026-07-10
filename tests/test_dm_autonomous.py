"""Autonomous DM tests (P6.4) — mocked provider, no real LLM."""

import json
import unittest
from unittest.mock import MagicMock

from engine.game_engine import GameEngine
from engine.dm_autonomous import MAX_COMMANDS_PER_DAY


def _plan(notes, commands):
    return json.dumps({"arc_notes": notes, "commands": commands})


class TestAutonomousDM(unittest.TestCase):
    def setUp(self):
        from tests import clean_dm_library
        clean_dm_library()
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()
        self.auto = self.engine.dm_autonomous

    def tearDown(self):
        from world.monsters import MONSTER_TEMPLATES
        for tid in list(self.engine.dm.defined_monsters):
            MONSTER_TEMPLATES.pop(tid, None)
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _pretend_llm(self, response):
        self.engine.llm_interface.provider_name = "anthropic"
        self.engine.llm_interface.generate_response = MagicMock(
            return_value=response)

    def test_heuristic_mode_never_plans(self):
        spy = MagicMock()
        self.engine.llm_interface.generate_response = spy
        self.assertEqual(self.auto.run_day(), [])
        spy.assert_not_called()

    def test_valid_plan_executes_and_updates_arc(self):
        px, py = self.engine.player.position
        self._pretend_llm(_plan(
            "Arc: the Gloom below the fen stirs. Planted: whispers.",
            [{"command": "narrate",
              "args": {"text": "Frogs have gone silent in the Murkfen."}},
             {"command": "define_monster",
              "args": {"template_id": "dm_gloom",
                       "spec": {"name": "The Gloom", "class": "monster",
                                "race": "goblin", "hp": 10,
                                "level": 1}}},
             {"command": "schedule_beat",
              "args": {"day": self.engine.dm._day() + 2,
                       "command": "spawn_npc",
                       "args": {"template_id": "dm_gloom",
                                "position": [px + 25, py + 25]}}}]))
        results = self.auto.run_day()
        self.assertEqual(len(results), 3)
        self.assertTrue(all(r["ok"] for r in results), results)
        self.assertIn("Gloom below the fen",
                      self.engine.dm.campaign_notes)
        log = " ".join(str(e) for e in
                       self.engine.memory_manager.game_history[-4:])
        self.assertIn("Frogs have gone silent", log)
        self.assertTrue(self.engine.dm.scheduled)

    def test_junk_plan_is_a_quiet_day(self):
        self._pretend_llm("The mists part and reveal... nothing useful.")
        self.assertEqual(self.auto.run_day(), [])
        self.assertTrue(any(e["command"] == "plan_day" and not e["ok"]
                            for e in self.engine.dm.notebook))

    def test_command_cap(self):
        commands = [{"command": "narrate",
                     "args": {"text": f"beat {i}"}}
                    for i in range(MAX_COMMANDS_PER_DAY + 5)]
        self._pretend_llm(_plan("spam arc", commands))
        results = self.auto.run_day()
        self.assertEqual(len(results), MAX_COMMANDS_PER_DAY)

    def test_charter_refusals_reported_not_fatal(self):
        px, py = self.engine.player.position
        self._pretend_llm(_plan("aggressive arc", [
            {"command": "spawn_npc",
             "args": {"template_id": "wolf",
                      "position": [px + 1, py]}},
            {"command": "narrate", "args": {"text": "Still standing."}}]))
        results = self.auto.run_day()
        self.assertFalse(results[0]["ok"])
        self.assertTrue(results[1]["ok"],
                        "one refusal must not stop the bundle")

    def test_forbidden_commands_skipped(self):
        self._pretend_llm(_plan("sneaky arc", [
            {"command": "run_scheduled", "args": {}},
            {"command": "digest", "args": {}}]))
        results = self.auto.run_day()
        self.assertEqual(results, [])

    def test_campaign_notes_persist_in_saves(self):
        import shutil
        import tempfile
        from engine.save_load import SaveManager
        self.engine.dm.campaign_notes = "Arc: the Gloom, act two."
        tmp = tempfile.mkdtemp()
        try:
            sm = SaveManager(save_dir=tmp)
            sm.save(self.engine, name="dma")
            self.engine.dm.campaign_notes = ""
            self.assertTrue(sm.load(self.engine, name="dma"))
            self.assertIn("act two", self.engine.dm.campaign_notes)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_day_change_triggers_planning_with_llm(self):
        self._pretend_llm(_plan("day arc", [
            {"command": "narrate", "args": {"text": "Dawn mists."}}]))
        now = self.engine.world.time
        self.engine.world.time = ((now // (24 * 60)) + 1) * 24 * 60
        self.engine.advance_turn()
        log = " ".join(str(e) for e in
                       self.engine.memory_manager.game_history[-15:])
        self.assertIn("[DM] Dawn mists.", log)


if __name__ == "__main__":
    unittest.main()
