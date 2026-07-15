"""Windows (P14.2): a physical, always-on glimpse into a building you stand
BESIDE — you see the folk inside through the window, but the wall still
keeps you from reaching them."""

import os as _os
import tempfile as _tempfile
_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_lib_"))

import unittest

from engine.game_engine import GameEngine
from engine.presence import (at_a_window, hidden_by_walls, is_indoors,
                             npc_adjacent_to_player)


class TestWindows(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False)
        self.engine.start_game()
        self.p = self.engine.player
        self.indoor = next(
            (n for n in self.engine.npc_manager.npcs.values()
             if n.is_active() and is_indoors(self.engine, n)), None)
        if self.indoor is None:
            loc = next(l for l in self.engine.world.locations
                       if l.name in self.engine.interiors)
            self.indoor = next(iter(self.engine.npc_manager.npcs.values()))
            self.indoor.position = (loc.x, loc.y)
        self.bldg = is_indoors(self.engine, self.indoor)
        self.loc = next(l for l in self.engine.world.locations
                        if l.name == self.bldg)

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _beside(self):
        # a street tile one step off the building's left edge
        self.p.position = (self.loc.x - 1, self.loc.y)

    def _far(self):
        fx = self.loc.x + self.loc.width + 4
        if fx >= self.engine.world.map.width - 1:
            fx = max(1, self.loc.x - 4)
        self.p.position = (fx, self.loc.y)

    def test_beside_the_building_is_at_a_window(self):
        self._beside()
        self.assertTrue(at_a_window(self.engine, self.bldg))

    def test_far_from_the_building_is_not(self):
        self._far()
        self.assertFalse(at_a_window(self.engine, self.bldg))

    def test_a_window_reveals_the_folk_inside(self):
        self._beside()
        self.assertFalse(hidden_by_walls(self.engine, self.indoor),
                         "beside the wall, you glimpse them through the window")

    def test_from_afar_the_walls_still_hide_them(self):
        self._far()
        self.assertTrue(hidden_by_walls(self.engine, self.indoor),
                        "no ordinary sight through a wall from across the way")

    def test_a_window_is_sight_not_reach(self):
        self._beside()
        self.assertFalse(npc_adjacent_to_player(self.engine, self.indoor),
                         "the window shows him, the wall keeps him")


if __name__ == "__main__":
    unittest.main()
