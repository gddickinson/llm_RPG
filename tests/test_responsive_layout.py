"""Responsive layout (PUX.4c): the screen regions are valid, non-
overlapping, and flex with the window at any size — not hard-pinned to
1280×800."""

import os as _os
import tempfile as _tempfile
import unittest

_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_lib_"))

from ui.gui import MIN_H, MIN_W, compute_layout      # noqa: E402

_PANELS = ("map", "status", "quests", "events", "minimap", "party")
_SIZES = [(1280, 800), (1600, 900), (1920, 1080), (1024, 720),
          (900, 640), (800, 600), (400, 300)]


class TestResponsiveLayout(unittest.TestCase):
    def test_regions_are_valid_and_disjoint_at_every_size(self):
        for w, h in _SIZES:
            lay = compute_layout(w, h)
            eff_w, eff_h = max(MIN_W, w), max(MIN_H, h)
            for name in _PANELS:
                r = lay[name]
                self.assertGreater(r.width, 0, (w, h, name))
                self.assertGreater(r.height, 0, (w, h, name))
                self.assertGreaterEqual(r.x, 0)
                self.assertGreaterEqual(r.y, 0)
                self.assertLessEqual(r.right, eff_w)
                self.assertLessEqual(r.bottom, eff_h)
            panels = [lay[n] for n in _PANELS]
            for i in range(len(panels)):
                for j in range(i + 1, len(panels)):
                    self.assertFalse(
                        panels[i].colliderect(panels[j]),
                        f"{_PANELS[i]} overlaps {_PANELS[j]} at {(w, h)}")

    def test_map_flexes_with_the_window(self):
        small = compute_layout(1000, 700)["map"]
        big = compute_layout(1700, 1000)["map"]
        self.assertGreater(big.width, small.width)
        self.assertGreater(big.height, small.height)

    def test_party_stays_bottom_right(self):
        lay = compute_layout(1280, 800)
        self.assertEqual(lay["party"].right, 1280)
        self.assertEqual(lay["party"].bottom, 800)

    def test_tiny_window_clamps_but_stays_valid(self):
        lay = compute_layout(200, 150)         # absurdly small
        for r in lay.values():
            self.assertGreater(r.width, 0)
            self.assertGreater(r.height, 0)


class TestGuiResize(unittest.TestCase):
    def test_resize_relays_the_screen(self):
        import pygame
        pygame.display.init()
        pygame.display.set_mode((1280, 800))
        from engine.game_engine import GameEngine
        from ui.gui import GameGUI
        engine = GameEngine(llm_provider="heuristic",
                            enable_npc_processes=False)
        engine.start_game()
        gui = GameGUI(engine)
        w0 = gui.layout["map"].width
        gui.resize(1600, 1000)
        self.assertEqual(gui.width, 1600)
        self.assertGreater(gui.layout["map"].width, w0)
        # never shrinks below the usable minimum
        gui.resize(300, 200)
        self.assertGreaterEqual(gui.width, MIN_W)
        self.assertGreaterEqual(gui.height, MIN_H)
        engine.end_game()


if __name__ == "__main__":
    unittest.main()
