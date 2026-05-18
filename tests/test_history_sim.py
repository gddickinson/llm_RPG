"""Tests for the pre-game history simulator."""

import unittest
import random

from world.history_sim import simulate, apply_history, EVENT_POOL
from engine.game_engine import GameEngine


class TestSimulate(unittest.TestCase):
    def test_returns_n_events(self):
        events = simulate(rng=random.Random(0), years=3)
        self.assertEqual(len(events), 3)

    def test_no_duplicates(self):
        events = simulate(rng=random.Random(0), years=5)
        descs = [e.description for e in events]
        self.assertEqual(len(set(descs)), len(descs))

    def test_capped_at_pool_size(self):
        events = simulate(years=100)
        self.assertEqual(len(events), len(EVENT_POOL))


class TestApplyHistory(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_ruined_keep_exists(self):
        names = [l.name for l in self.engine.world.locations]
        self.assertIn("Ruined Keep", names)

    def test_lore_in_event_log(self):
        history = self.engine.memory_manager.get_recent_history(20)
        lore_lines = [e for e in history if "[Lore]" in e]
        self.assertTrue(lore_lines)


if __name__ == "__main__":
    unittest.main()
