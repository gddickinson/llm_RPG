"""Regression tests for the NPC message-flood bug (playtest report).

Standing next to a talkative NPC flooded the event log: the GUI drives
NPC processing every frame (30/s) and the only gate was
`turn_counter % INTERVAL == 0` — true continuously while idle.
"""

import unittest

from engine.game_engine import GameEngine


class TestNpcCadence(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_frame_loop_does_not_flood_while_idle(self):
        """Simulate the 30 FPS GUI loop with a static turn counter:
        NPCs must act at most once (turn tick) — not 100 times."""
        self.engine.turn_counter = 0  # multiple of the interval
        log_before = len(self.engine.memory_manager.game_history)
        for _ in range(100):
            self.engine.process_npc_turns_async()
        new_events = len(self.engine.memory_manager.game_history) \
            - log_before
        # One batch of NPC actions max (a few nearby NPCs), not 100
        self.assertLess(new_events, 15,
                        f"{new_events} events from 100 idle frames — "
                        f"the flood is back")

    def test_npcs_still_act_on_turn_cadence(self):
        import config
        self.engine._npc_last_time = 0.0
        self.engine._npc_last_turn = None
        self.engine.turn_counter = config.NPC_ACTION_INTERVAL
        self.assertTrue(self.engine._npc_turns_due(),
                        "interval turns must trigger NPC actions")
        # Same turn again (another frame): not due
        self.assertFalse(self.engine._npc_turns_due())

    def test_idle_wall_clock_tick_keeps_world_alive(self):
        import time
        self.engine._npc_turns_due()          # consume
        self.engine._npc_last_time = time.monotonic() - 10.0
        self.assertTrue(self.engine._npc_turns_due(),
                        "a long-idle player should still see NPCs act")

    def test_consecutive_duplicate_events_suppressed(self):
        mm = self.engine.memory_manager
        before = len(mm.game_history)
        mm.add_event("Goren sleeps peacefully.")
        mm.add_event("Goren sleeps peacefully.")
        mm.add_event("Goren sleeps peacefully.")
        self.assertEqual(len(mm.game_history), before + 1)
        # Different events still append
        mm.add_event("Goren wakes.")
        mm.add_event("Goren sleeps peacefully.")
        self.assertEqual(len(mm.game_history), before + 3)


if __name__ == "__main__":
    unittest.main()
