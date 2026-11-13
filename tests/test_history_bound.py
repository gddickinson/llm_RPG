"""The event history stays bounded (config.MAX_HISTORY_ITEMS), and the away
digest still reports a long absence (it keeps its own record of the lines it
needs instead of slicing the bounded history)."""

import unittest

from engine.memory_manager import MemoryManager


class TestHistoryBound(unittest.TestCase):
    def test_history_is_trimmed_on_add(self):
        mm = MemoryManager(max_history=5)
        for i in range(20):
            mm.add_event(f"event {i}")
        self.assertEqual(len(mm.game_history), 5)
        self.assertEqual(mm.game_history[-1]["event"], "event 19")
        self.assertEqual(mm.game_history[0]["event"], "event 15")

    def test_observers_still_see_every_event(self):
        mm = MemoryManager(max_history=3)
        seen = []
        mm.add_observer(seen.append)
        for i in range(10):
            mm.add_event(f"e{i}")
        self.assertEqual(len(seen), 10)


class TestAwayDigestLongAbsence(unittest.TestCase):
    def setUp(self):
        from engine.game_engine import GameEngine
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False)
        self.engine.start_game()
        self.p = self.engine.player

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_deeds_survive_more_events_than_the_history_holds(self):
        mm = self.engine.memory_manager
        self.engine.roster.set_away(self.p, True)
        mm.add_event(f"[Away] {self.p.name} slew a cave bear")
        mm.add_event("Quest accepted: The Burning Road")
        for i in range(mm.max_history * 3):
            mm.add_event(f"filler {i}")
        self.assertLessEqual(len(mm.game_history), mm.max_history)
        from engine.away_digest import build_digest
        title, lines = build_digest(self.engine, self.p)
        text = "\n".join(lines)
        self.assertIn("slew a cave bear", text)
        self.assertIn("took on 1 quest", text)


if __name__ == "__main__":
    unittest.main()
