"""Sleep + day summary tests (P5.6)."""

import unittest

from engine.game_engine import GameEngine
from engine.rest import sleep, can_sleep_here, BED_COST, WAKE_HOUR


class TestRest(unittest.TestCase):
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

    def _enter_tavern(self):
        tavern_key = next((k for k in self.engine.interiors
                           if "tavern" in k.lower() or
                           "inn" in k.lower()), None)
        if tavern_key is None:
            self.skipTest("no tavern interior")
        self.engine.current_interior = self.engine.interiors[tavern_key]

    def test_no_bed_in_the_wilds(self):
        self.player.position = (2, 2)
        self.assertIsNotNone(can_sleep_here(self.engine))
        self.assertEqual(sleep(self.engine), [])

    def test_sleep_at_tavern_restores_and_advances(self):
        self._enter_tavern()
        self.player.gold = 50
        self.player.hp = 3
        self.player.metadata["hunger"] = 80
        t0 = self.engine.world.time
        lines = sleep(self.engine)
        self.assertTrue(lines)
        self.assertEqual(self.player.hp, self.player.max_hp)
        self.assertLessEqual(self.player.metadata["hunger"], 5)
        self.assertEqual(self.player.gold, 45, "bed costs 5g")
        # Woke at dawn the next day
        new_time = self.engine.world.time
        self.assertGreater(new_time, t0)
        minute_of_day = new_time % (24 * 60)
        self.assertAlmostEqual(minute_of_day, WAKE_HOUR * 60, delta=5)

    def test_sleep_refused_when_broke(self):
        self._enter_tavern()
        self.player.gold = BED_COST - 1
        self.assertEqual(sleep(self.engine), [])
        log = " ".join(str(e) for e in
                       self.engine.memory_manager.game_history[-2:])
        self.assertIn("can't cover", log)

    def test_summary_reports_the_days_earnings(self):
        self._enter_tavern()
        self.player.gold = 100
        base = dict(self.engine._day_metrics)
        base["gold"] = 40      # pretend dawn gold was 40
        self.engine._day_metrics = base
        lines = sleep(self.engine)
        text = "\n".join(lines)
        self.assertIn("Gold: +55", text)   # 100 - 5 bed - 40
        self.assertIn("tavern board", text)

    def test_sleeping_fires_the_nightly_stack(self):
        self._enter_tavern()
        self.player.gold = 50
        sleep(self.engine)
        log = " ".join(str(e) for e in
                       self.engine.memory_manager.game_history[-20:])
        self.assertIn("[Realm]", log, "faction ticker should have run")

    def test_metrics_reset_after_sleep(self):
        self._enter_tavern()
        self.player.gold = 200
        sleep(self.engine)
        self.assertEqual(self.engine._day_metrics["gold"],
                         self.player.gold,
                         "a fresh dawn snapshot after waking")

    def test_quiet_day_message(self):
        self._enter_tavern()
        self.player.gold = 50
        self.engine._day_metrics = __import__(
            "engine.rest", fromlist=["snapshot"]).snapshot(self.engine)
        # Adjust for the bed cost so gold delta is the only change
        lines = sleep(self.engine)
        text = "\n".join(lines)
        self.assertIn("quiet day", text.lower())

    def test_hint_advertises_the_bed(self):
        from ui.hints import context_hints
        self._enter_tavern()
        hints = context_hints(self.engine)
        self.assertTrue(any("sleep until morning" in h for h in hints),
                        hints)


if __name__ == "__main__":
    unittest.main()
