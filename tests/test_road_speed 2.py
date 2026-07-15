"""Roads earn their keep (P15.8): fast ground banks free steps."""

import os as _os
import tempfile as _tempfile
import unittest

_os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
_os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_lib_"))

from engine.game_engine import GameEngine            # noqa: E402
from engine.traversal import ROAD_FREE_EVERY, MOUNT_FREE_EVERY  # noqa: E402
from world.world_map import TerrainType              # noqa: E402


class TestRoadPace(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False)
        self.engine.start_game()
        self.p = self.engine.player

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _stand_on(self, terrain):
        x, y = self.p.position
        self.engine.world.map.terrain[y][x] = terrain

    # ---- the pace counter (pure-ish) --------------------------------

    def test_free_every_third_road_step(self):
        self._stand_on(TerrainType.ROAD)
        self.p.metadata["road_steps"] = 0
        res = [self.engine.traversal._road_pace() for _ in range(6)]
        self.assertEqual(res, [False, False, True, False, False, True])

    def test_a_mount_frees_every_second(self):
        self._stand_on(TerrainType.ROAD)
        self.p.metadata["road_steps"] = 0
        self.p.metadata["mounted"] = True
        res = [self.engine.traversal._road_pace() for _ in range(6)]
        self.assertEqual(res, [False, True, False, True, False, True])

    def test_bridges_count_as_fast_ground(self):
        self._stand_on(TerrainType.BRIDGE)
        self.p.metadata["road_steps"] = ROAD_FREE_EVERY - 1
        self.assertTrue(self.engine.traversal._road_pace())

    def test_open_ground_never_frees_and_resets(self):
        self._stand_on(TerrainType.GRASS)
        self.p.metadata["road_steps"] = 2
        self.assertFalse(self.engine.traversal._road_pace())
        self.assertEqual(self.p.metadata["road_steps"], 0)

    # ---- the world clock --------------------------------------------

    def test_free_road_step_skips_the_world_tick(self):
        self._stand_on(TerrainType.ROAD)
        self.p.metadata["road_steps"] = ROAD_FREE_EVERY - 1   # next = free
        tc0 = self.engine.turn_counter
        self.engine.traversal.advance_after_move()
        self.assertEqual(self.engine.turn_counter, tc0)

    def test_ordinary_road_step_ticks(self):
        self._stand_on(TerrainType.ROAD)
        self.p.metadata["road_steps"] = 0                     # next = not free
        tc0 = self.engine.turn_counter
        self.engine.traversal.advance_after_move()
        self.assertEqual(self.engine.turn_counter, tc0 + 1)

    def test_six_road_strides_cost_fewer_turns_than_open_ground(self):
        self._stand_on(TerrainType.ROAD)
        self.p.metadata["road_steps"] = 0
        tc0 = self.engine.turn_counter
        for _ in range(6):
            self.engine.traversal.advance_after_move()
        road_turns = self.engine.turn_counter - tc0
        self.assertEqual(road_turns, 4)          # 2 of 6 strides were free

        self._stand_on(TerrainType.GRASS)
        tc1 = self.engine.turn_counter
        for _ in range(6):
            self.engine.traversal.advance_after_move()
        open_turns = self.engine.turn_counter - tc1
        self.assertEqual(open_turns, 6)
        self.assertLess(road_turns, open_turns)

    def test_the_road_advertises_itself_once(self):
        self._stand_on(TerrainType.ROAD)
        self.p.metadata["road_steps"] = 0
        self.p.metadata.pop("road_hint_shown", None)
        for _ in range(ROAD_FREE_EVERY):
            self.engine.traversal.advance_after_move()
        hist = self.engine.memory_manager.get_recent_history(20)
        self.assertTrue(any("good time on the road" in h for h in hist))
        self.assertTrue(self.p.metadata.get("road_hint_shown"))


if __name__ == "__main__":
    unittest.main()
