"""Battle Testbed menu: every scenario must fit the page (the list grew
past a single scrollless column) and stay keyboard-navigable."""

import os as _os
import unittest

_os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
_os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame                                            # noqa: E402
pygame.init()
pygame.display.set_mode((1024, 700))

from ui.start_menu import StartMenu                      # noqa: E402


class TestBattleMenuLayout(unittest.TestCase):
    def setUp(self):
        self.m = StartMenu()
        self.m._refresh_scenarios()
        self.m.state = "battle_menu"

    def test_there_are_scenarios(self):
        self.assertGreater(len(self.m.scenarios), 10)

    def test_every_scenario_fits_the_grid(self):
        cols, rows, _, _ = self.m._grid_dims()
        self.assertGreaterEqual(cols * rows, len(self.m.scenarios),
                                "some battles would fall off the page")

    def test_no_row_runs_off_the_bottom(self):
        cols, rows, row_h, top = self.m._grid_dims()
        for i in range(len(self.m.scenarios)):
            col, row = i // rows, i % rows
            self.assertLess(col, cols, "no scenario is placed off-grid")
            self.assertLess(top + row * row_h, self.m.height - 40)

    def test_renders_without_crashing(self):
        self.m._render_scenario_list()

    def test_navigation_stays_in_bounds(self):
        n = len(self.m.scenarios)
        self.m.selected = 0
        for key in (pygame.K_RIGHT, pygame.K_DOWN, pygame.K_LEFT,
                    pygame.K_UP, pygame.K_RIGHT, pygame.K_RIGHT):
            self.m._battle_key(key)
            self.assertTrue(0 <= self.m.selected < n)

    def test_enter_returns_the_selected_battle(self):
        self.m.selected = 3
        out = self.m._battle_key(pygame.K_RETURN)
        self.assertEqual(out["action"], "battle")
        self.assertEqual(out["scenario"], self.m.scenarios[3][0])

    def test_left_right_jump_columns(self):
        _, rows, _, _ = self.m._grid_dims()
        n = len(self.m.scenarios)
        self.m.selected = 0
        self.m._battle_key(pygame.K_RIGHT)          # into the next column
        self.assertEqual(self.m.selected, rows % n)


if __name__ == "__main__":
    unittest.main()
