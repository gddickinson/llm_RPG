"""OAKVALE — the visible sewer-grate Deepdelve entrance (pure, headless)."""

import unittest

import pygame

from ui import grate


class TestGrateGeometry(unittest.TestCase):
    def test_shaft_and_frame_within_the_tile(self):
        g = grate.grate_geometry(100, 200, 48)
        fx, fy, fw, fh = g["frame"]
        self.assertGreaterEqual(fx, 100)
        self.assertLessEqual(fx + fw, 100 + 48)
        sx, sy, sw, sh = g["shaft"]
        self.assertGreater(sw, 0)
        self.assertGreater(sh, 0)

    def test_has_bars(self):
        g = grate.grate_geometry(0, 0, 48)
        self.assertGreaterEqual(len(g["vbars"]), 2, "vertical bars")
        self.assertGreaterEqual(len(g["hbars"]), 2, "cross bars")

    def test_draws_headless(self):
        surf = pygame.Surface((80, 80))
        grate.draw_grate(surf, 10, 10, 48)
        grate.draw_grate(surf, 0, 0, 6)          # tiny tile early-out


if __name__ == "__main__":
    unittest.main()
