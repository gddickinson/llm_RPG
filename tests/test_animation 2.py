"""Animation math (P15.2) — the pure functions behind the pixels."""

import unittest

from ui.animation import (clamp, lerp, smoothstep, lerp_color,
                          frame_index, surface_fill, ambient_darkness)


class TestInterpolation(unittest.TestCase):
    def test_clamp(self):
        self.assertEqual(clamp(5, 0, 10), 5)
        self.assertEqual(clamp(-1, 0, 10), 0)
        self.assertEqual(clamp(99, 0, 10), 10)

    def test_lerp_endpoints_and_mid(self):
        self.assertEqual(lerp(0, 10, 0.0), 0)
        self.assertEqual(lerp(0, 10, 1.0), 10)
        self.assertEqual(lerp(0, 10, 0.5), 5)

    def test_smoothstep_is_flat_at_the_ends(self):
        self.assertEqual(smoothstep(0.0), 0.0)
        self.assertEqual(smoothstep(1.0), 1.0)
        self.assertEqual(smoothstep(0.5), 0.5)
        # eased: below the diagonal in the first half
        self.assertLess(smoothstep(0.25), 0.25)
        self.assertGreater(smoothstep(0.75), 0.75)
        # clamps out-of-range input
        self.assertEqual(smoothstep(-1.0), 0.0)
        self.assertEqual(smoothstep(2.0), 1.0)

    def test_lerp_color(self):
        self.assertEqual(lerp_color((0, 0, 0), (255, 255, 255), 0.0),
                         (0, 0, 0))
        self.assertEqual(lerp_color((0, 0, 0), (255, 255, 255), 1.0),
                         (255, 255, 255))
        self.assertEqual(lerp_color((0, 0, 0), (10, 20, 30), 0.5),
                         (5, 10, 15))
        # RGBA passes through the alpha channel too
        self.assertEqual(lerp_color((0, 0, 0, 0), (100, 100, 100, 200), 0.5),
                         (50, 50, 50, 100))


class TestFrameIndex(unittest.TestCase):
    def test_static_kinds_never_animate(self):
        for kind in ("oil", "blood", "unknown"):
            for t in (0.0, 0.5, 3.7, 100.0):
                self.assertEqual(frame_index(t, kind), 0)

    def test_fire_alternates_over_time(self):
        # 0.12s per frame -> frame 0 in [0,0.12), frame 1 in [0.12,0.24)
        self.assertEqual(frame_index(0.0, "fire"), 0)
        self.assertEqual(frame_index(0.06, "fire"), 0)
        self.assertEqual(frame_index(0.13, "fire"), 1)
        self.assertEqual(frame_index(0.25, "fire"), 0)   # wrapped

    def test_negative_clock_is_frame_zero(self):
        self.assertEqual(frame_index(-1.0, "fire"), 0)


class TestSurfaceFill(unittest.TestCase):
    def test_fire_is_brighter_on_the_flicker_frame(self):
        dim = surface_fill("fire", 0.0)
        bright = surface_fill("fire", 0.13)
        self.assertEqual(dim[:3], (250, 120, 20))
        self.assertGreater(bright[3], dim[3])          # alpha pulses up

    def test_static_surfaces_ignore_the_clock(self):
        for kind in ("oil", "blood"):
            self.assertEqual(surface_fill(kind, 0.0),
                             surface_fill(kind, 5.5))

    def test_electrified_crackles_within_valid_alpha(self):
        for t in (0.0, 0.07, 0.5, 2.3):
            c = surface_fill("electrified", t)
            self.assertEqual(c[:3], (150, 220, 255))
            self.assertTrue(0 <= c[3] <= 255)

    def test_unknown_kind_falls_back_to_water_default(self):
        self.assertEqual(surface_fill("mystery", 0.0), (60, 120, 220, 90))

    def test_every_fill_is_valid_rgba(self):
        for kind in ("fire", "oil", "blood", "electrified", "water", "x"):
            c = surface_fill(kind, 1.0)
            self.assertEqual(len(c), 4)
            self.assertTrue(all(0 <= ch <= 255 for ch in c))


class TestAmbientDarkness(unittest.TestCase):
    def test_noon_is_bright(self):
        self.assertEqual(ambient_darkness(12.0), 0)

    def test_deep_night_is_dark(self):
        self.assertGreater(ambient_darkness(2.0), 150)
        self.assertGreater(ambient_darkness(23.0), 150)

    def test_matches_the_old_anchors(self):
        # evening (~18:30) sits near the old 80; night (>=21:30) at ~170
        self.assertGreater(ambient_darkness(18.5), 40)
        self.assertLess(ambient_darkness(18.5), 120)
        self.assertGreater(ambient_darkness(21.5), 150)

    def test_dusk_ramps_up_monotonically(self):
        vals = [ambient_darkness(h) for h in (16.5, 17.5, 18.5, 19.5, 20.5)]
        self.assertEqual(vals, sorted(vals))
        self.assertLess(vals[0], vals[-1])

    def test_dawn_ramps_down_monotonically(self):
        vals = [ambient_darkness(h) for h in (4.5, 5.5, 6.5, 7.0)]
        self.assertEqual(vals, sorted(vals, reverse=True))

    def test_no_snap_small_step_small_change(self):
        # the whole point: a minute never jumps the sky by a huge step
        prev = ambient_darkness(0.0)
        for i in range(1, 24 * 60):
            cur = ambient_darkness(i / 60.0)
            self.assertLessEqual(abs(cur - prev), 3)
            prev = cur

    def test_wraps_past_midnight(self):
        self.assertEqual(ambient_darkness(0.0), ambient_darkness(24.0))


if __name__ == "__main__":
    unittest.main()
