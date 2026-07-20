"""BLD.7 — architectural facade trim geometry (pure, headless).

Shutters + sills/lintels around windows, cornice + quoins on the front — the
detail `renderer_buildings` lays over the 2.5D building blocks. These check the
pure geometry and that the thin draws don't blow up headless.
"""

import unittest

import pygame

from ui import facade_trim as ft


class TestTrimStyle(unittest.TestCase):
    def test_grand_gets_the_full_dress(self):
        for kind in ("temple", "cathedral", "hall", "keep", "library"):
            s = ft.trim_style_for(kind)
            self.assertTrue(s["quoins"] and s["cornice"] and s["lintel"],
                            f"{kind} is a grand building")
            self.assertTrue(s["shutters"] and s["sill"])

    def test_plain_home_just_shutters_and_sill(self):
        s = ft.trim_style_for("home")
        self.assertTrue(s["shutters"] and s["sill"])
        self.assertFalse(s["quoins"] or s["cornice"] or s["lintel"])


class TestWindowTrim(unittest.TestCase):
    def _w(self):
        return (100, 200, 12, 10)

    def test_shutters_flank_without_covering_the_window(self):
        x, y, w, h = self._w()
        left, right = ft.shutter_rects(x, y, w, h)
        self.assertLessEqual(left[0] + left[2], x, "left shutter is left of glass")
        self.assertGreaterEqual(right[0], x + w, "right shutter is right of glass")
        # same height as the window, so they read as a pair
        self.assertEqual(left[3], h)
        self.assertEqual(right[3], h)

    def test_sill_below_lintel_above(self):
        x, y, w, h = self._w()
        sill = ft.sill_rect(x, y, w, h)
        lintel = ft.lintel_rect(x, y, w, h)
        self.assertGreaterEqual(sill[1], y + h, "sill sits under the window")
        self.assertLessEqual(lintel[1] + lintel[3], y, "lintel sits over it")
        # both a touch wider than the opening
        self.assertGreater(sill[2], w)
        self.assertGreater(lintel[2], w)


class TestCornerTrim(unittest.TestCase):
    def test_cornice_rides_the_eave(self):
        ts, h, sx, sy = 48, 40, 100, 200
        c = ft.cornice_rect(sx, sy, ts, h)
        self.assertIsNotNone(c)
        eave = sy + ts - h
        self.assertEqual(c[1], eave)
        self.assertEqual(c[2], ts, "spans the block width")

    def test_cornice_none_on_a_tiny_block(self):
        self.assertIsNone(ft.cornice_rect(0, 0, 8, 2))

    def test_quoins_climb_both_corners(self):
        ts, h, sx, sy = 48, 40, 100, 200
        blocks = ft.quoin_blocks(sx, sy, ts, h)
        self.assertTrue(blocks)
        xs = {b[0] for b in blocks}
        self.assertIn(sx, xs, "a left-corner column")
        self.assertTrue(any(abs(b[0] - (sx + ts - b[2])) <= 1 for b in blocks),
                        "a right-corner column")

    def test_quoins_empty_on_a_small_block(self):
        self.assertEqual(ft.quoin_blocks(0, 0, 12, 6), [])

    def test_span_quoins_at_outer_corners(self):
        blocks = ft.span_quoin_blocks(100, 200, 240, 96, 48)
        self.assertTrue(blocks)
        xs = {b[0] for b in blocks}
        self.assertIn(100, xs)
        self.assertTrue(any(b[0] + b[2] == 100 + 96 for b in blocks))


class TestDrawsHeadless(unittest.TestCase):
    def setUp(self):
        self.surf = pygame.Surface((300, 300))

    def test_draws_do_not_crash(self):
        style = ft.trim_style_for("temple")
        ft.draw_window_trim(self.surf, (120, 210, 12, 10), style, 48)
        ft.draw_corner_trim(self.surf, 100, 200, 48, 40, style)
        ft.draw_span_corner_trim(self.surf, 100, 200, 296, 96, 48, style)
        # tiny tile → early-outs, still no crash
        ft.draw_window_trim(self.surf, (10, 10, 2, 2),
                            ft.trim_style_for("home"), 8)


if __name__ == "__main__":
    unittest.main()
