"""Off-screen faction ticker tests (P5.4)."""

import unittest

from engine.game_engine import GameEngine
from engine.faction_ticker import DEFAULT_STATE, STRONG, LOW_STORES


class TestFactionTicker(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()
        self.ticker = self.engine.faction_ticker

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_daily_event_moves_numbers_and_logs(self):
        before = {k: dict(v) for k, v in self.ticker.state.items()}
        notes = self.ticker.run_day()
        self.assertTrue(notes)
        self.assertNotEqual(self.ticker.state, before,
                            "an event must move faction numbers")
        log = " ".join(str(e) for e in
                       self.engine.memory_manager.game_history[-4:])
        self.assertIn("[Realm]", log)

    def test_events_become_rumors(self):
        self.engine.world_director.rumors = []
        self.ticker.run_day()
        self.assertTrue(self.engine.world_director.rumors,
                        "ticker events should enter the rumor pool")

    def test_low_village_stores_triggers_shortage(self):
        self.ticker.state["villagers"]["stores"] = LOW_STORES - 5
        notes = self.ticker._consequences()
        self.assertTrue(any("short" in n.lower() for n in notes))
        director = self.engine.world_director
        surged = any(director.shortage_multiplier(i) > 1.0
                     for i in ("bread", "ale"))
        self.assertTrue(surged, "hungry villages should raise prices")

    def test_strong_brigands_raise_bandit_encounters(self):
        self.ticker.state["brigands"]["strength"] = STRONG + 10
        self.assertEqual(self.ticker.bandit_weight_multiplier(), 2.0)
        self.ticker.state["brigands"]["strength"] = 20
        self.assertEqual(self.ticker.bandit_weight_multiplier(), 0.5)

    def test_numbers_clamp(self):
        self.ticker.state["brigands"]["strength"] = 4
        self.ticker._clamp()
        self.assertGreaterEqual(
            self.ticker.state["brigands"]["strength"], 5)
        self.ticker.state["villagers"]["stores"] = 400
        self.ticker._clamp()
        self.assertLessEqual(
            self.ticker.state["villagers"]["stores"], 100)

    def test_day_change_runs_ticker(self):
        now = self.engine.world.time
        self.engine.world.time = ((now // (24 * 60)) + 1) * 24 * 60
        self.engine.advance_turn()
        log = " ".join(str(e) for e in
                       self.engine.memory_manager.game_history[-12:])
        self.assertIn("[Realm]", log)

    def test_state_persists_in_saves(self):
        import shutil
        import tempfile
        from engine.save_load import SaveManager
        self.ticker.state["brigands"]["strength"] = 77
        tmp = tempfile.mkdtemp()
        try:
            sm = SaveManager(save_dir=tmp)
            sm.save(self.engine, name="ft")
            self.ticker.state["brigands"]["strength"] = 10
            self.assertTrue(sm.load(self.engine, name="ft"))
            self.assertEqual(
                self.engine.faction_ticker.state["brigands"]["strength"],
                77)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_raid_resolution_both_ways(self):
        self.ticker.rng.randint = lambda a, b: 10   # attackers roll high
        self.ticker.state["brigands"]["strength"] = 90
        self.ticker.state["guards"]["strength"] = 10
        notes = self.ticker._brigand_raid()
        self.assertIn("got away", notes[0])
        self.ticker.rng.randint = lambda a, b: 1
        self.ticker.state["brigands"]["strength"] = 10
        self.ticker.state["guards"]["strength"] = 90
        notes = self.ticker._brigand_raid()
        self.assertIn("repelled", notes[0])


if __name__ == "__main__":
    unittest.main()
