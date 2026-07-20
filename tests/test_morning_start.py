"""A fresh new game begins at MORNING, not midnight (George 2026-07-15: "the
tiles are still mainly black"). Starting at 00:00 with an unexplored map meant
a new player woke to a tiny torch-pool in a sea of black fog and thought the
graphics were broken. Every world_kind now starts in daylight.
"""

import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
import tempfile
os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                      tempfile.mkdtemp(prefix="llmrpg_morn_"))

import unittest

from engine.game_engine import GameEngine


class TestMorningStart(unittest.TestCase):
    def _hour(self, eng):
        return (eng.world.time // 60) % 24

    def test_default_world_starts_in_daylight(self):
        e = GameEngine(llm_provider="heuristic", enable_npc_processes=False)
        e.start_game()
        try:
            hour = self._hour(e)
            self.assertGreaterEqual(hour, 6, "new game should start after dawn")
            self.assertLess(hour, 18, "new game should start before dusk")
        finally:
            try:
                e.end_game()
            except Exception:
                pass

    def test_time_of_day_is_not_night(self):
        e = GameEngine(llm_provider="heuristic", enable_npc_processes=False)
        e.start_game()
        try:
            self.assertNotEqual(e.world.get_time_of_day(), "night")
        finally:
            try:
                e.end_game()
            except Exception:
                pass


if __name__ == "__main__":
    unittest.main()
