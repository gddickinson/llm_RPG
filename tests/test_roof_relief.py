"""BLD.8 — roof relief, depth & weathering geometry (pure, headless).

Eaves/soffit depth, ridge caps, dormers, and deterministic per-building
weathering (so clones differ). These check the pure geometry + that the thin
draws don't blow up headless.
"""

import unittest

import pygame

from ui import roof_relief as rr


class TestWeathering(unittest.TestCase):
    def test_deterministic_per_world_position(self):
        a = rr.weathering_spots(12, 7, 100, 100, 48, 48)
        b = rr.weathering_spots(12, 7, 100, 100, 48, 48)
        self.assertEqual(a, b, "same building → same weathering every frame")

    def test_clones_differ(self):
        a = rr.weathering_spots(12, 7, 100, 100, 48, 48)
        b = rr.weathering_spots(13, 7, 100, 100, 48, 48)
        self.assertNotEqual(a, b, "a neighbour weathers differently")

    def test_spots_within_the_roof_rect(self):
        spots = rr.weathering_spots(3, 9, 100, 200, 48, 48, n=6)
        self.assertEqual(len(spots), 6)
        for (px, py, r, moss) in spots:
            self.assertTrue(100 <= px < 100 + 48)
            self.assertTrue(200 <= py < 200 + 48)
            self.assertGreaterEqual(r, 1)
            self.assertIn(moss, (True, False))

    def test_empty_on_a_tiny_roof(self):
        self.assertEqual(rr.weathering_spots(1, 1, 0, 0, 4, 2), [])


class TestEaves(unittest.TestCase):
    def test_soffit_band_under_the_eave(self):
        sx, eave_y, w, ts = 100, 240, 48, 48
        r = rr.soffit_rect(sx, eave_y, w, ts)
        self.assertEqual(r[0], sx)
        self.assertEqual(r[1], eave_y)
        self.assertEqual(r[2], w)
        self.assertGreaterEqual(r[3], 1, "a band with real height")


class TestDormers(unittest.TestCase):
    def test_none_on_a_narrow_roof(self):
        # width < 2*ts → no room for a dormer
        self.assertEqual(rr.dormer_boxes(0, 0, 48, 48, 48), [])

    def test_one_or_two_on_a_wide_roof(self):
        boxes = rr.dormer_boxes(0, 0, 48, 48 * 3, 48)
        self.assertIn(len(boxes), (1, 2))
        for (dx, dy, dw, dh) in boxes:
            self.assertGreaterEqual(dx, 0)
            self.assertLess(dx + dw, 48 * 3 + 1)
            self.assertGreater(dw, 0)
            self.assertGreater(dh, 0)

    def test_dormers_sit_on_the_slope(self):
        roof_top, eave_y = 100, 148
        boxes = rr.dormer_boxes(0, roof_top, eave_y, 48 * 3, 48)
        for (dx, dy, dw, dh) in boxes:
            self.assertGreater(dy, roof_top, "below the ridge")
            self.assertLessEqual(dy + dh, eave_y + 1, "above the eave")


class TestDrawsHeadless(unittest.TestCase):
    def setUp(self):
        self.surf = pygame.Surface((400, 400))
        self.shades = {"lit": (200, 180, 120), "shadow": (90, 80, 60),
                       "mid": (140, 120, 90), "ridge": (220, 200, 150)}

    def test_draws_do_not_crash(self):
        rr.draw_eaves(self.surf, 100, 240, 48, 48, (120, 100, 70))
        rr.draw_ridge_cap(self.surf, (100, 120), (148, 120), self.shades, 48)
        rr.draw_weathering(
            self.surf, rr.weathering_spots(2, 3, 100, 100, 48, 48),
            (100, 100, 48, 48))
        rr.draw_dormers(
            self.surf, rr.dormer_boxes(100, 100, 148, 144, 48), self.shades, 48)
        # a tiny tile early-outs cleanly
        rr.draw_eaves(self.surf, 0, 0, 8, 8, (100, 100, 100))

    def test_clip_is_restored(self):
        self.surf.set_clip((5, 5, 10, 10))
        rr.draw_weathering(
            self.surf, rr.weathering_spots(1, 1, 0, 0, 48, 48),
            (0, 0, 48, 48))
        self.assertEqual(self.surf.get_clip(), pygame.Rect(5, 5, 10, 10),
                         "the caller's clip survives")


if __name__ == "__main__":
    unittest.main()
