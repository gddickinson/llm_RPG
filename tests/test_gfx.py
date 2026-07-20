"""P40.1 gfx foundation — the reusable supersample + layered-shading
primitives behind the higher-fidelity procedural sprites. All headless:
build a Surface, assert its shape / that it's richer than a flat fill.
"""

import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import unittest

import pygame
pygame.init()

from ui import gfx


class TestSupersample(unittest.TestCase):
    def test_returns_target_size(self):
        s = gfx.supersample(
            lambda S: gfx.vgradient(S, (200, 180, 120), (90, 70, 40)), 48, ss=3)
        self.assertEqual(s.get_size(), (48, 48))

    def test_ss_one_is_native(self):
        s = gfx.supersample(lambda S: pygame.Surface((S, S)), 32, ss=1)
        self.assertEqual(s.get_size(), (32, 32))

    def test_ss_factor_env_override(self):
        os.environ["LLM_RPG_SS"] = "1"
        try:
            self.assertEqual(gfx.ss_factor(3), 1)
        finally:
            del os.environ["LLM_RPG_SS"]
        self.assertEqual(gfx.ss_factor(3), 3)

    def test_ss_factor_clamped(self):
        os.environ["LLM_RPG_SS"] = "99"
        try:
            self.assertLessEqual(gfx.ss_factor(3), 4)
        finally:
            del os.environ["LLM_RPG_SS"]


class TestColour(unittest.TestCase):
    def test_shade_ramp_orders_dark_to_light(self):
        ramp = gfx.shade_ramp((100, 150, 70), 5)
        self.assertEqual(len(ramp), 5)
        self.assertLess(sum(ramp[0]), sum(ramp[-1]))   # first is darkest

    def test_lerp_and_scale(self):
        self.assertEqual(gfx.lerp_rgb((0, 0, 0), (100, 100, 100), 0.5),
                         (50, 50, 50))
        self.assertEqual(gfx.scale_rgb((100, 100, 100), 2.0),
                         (200, 200, 200))
        # clamps
        self.assertEqual(gfx.scale_rgb((200, 200, 200), 2.0), (255, 255, 255))


class TestLayers(unittest.TestCase):
    def test_vgradient_is_not_flat(self):
        g = gfx.vgradient(48, (200, 180, 120), (90, 70, 40))
        self.assertEqual(g.get_size(), (48, 48))
        self.assertNotEqual(g.get_at((0, 0))[:3], g.get_at((0, 47))[:3])

    def test_mottle_changes_pixels(self):
        base = gfx.vgradient(48, (100, 150, 70), (100, 150, 70))  # flat
        before = pygame.image.tostring(base, "RGB")
        gfx.mottle(base, gfx.shade_ramp((100, 150, 70), 5), 7)
        after = pygame.image.tostring(base, "RGB")
        self.assertNotEqual(before, after, "mottle should add texture")

    def test_directional_light_has_alpha(self):
        dl = gfx.directional_light(48)
        self.assertTrue(dl.get_flags() & pygame.SRCALPHA)
        self.assertEqual(dl.get_size(), (48, 48))

    def test_soft_shadow_fades_out(self):
        ss = gfx.soft_shadow(48)
        self.assertGreater(ss.get_at((24, 24))[3], ss.get_at((2, 2))[3])

    def test_contact_shadow_sits_low(self):
        cs = gfx.contact_shadow(48)
        self.assertTrue(cs.get_flags() & pygame.SRCALPHA)
        # darker near the bottom-centre than the top (it grounds a prop)
        self.assertGreaterEqual(cs.get_at((24, 40))[3], cs.get_at((24, 6))[3])


class TestTileFidelity(unittest.TestCase):
    """The whole point: a built tile is no longer a flat fill."""
    def test_tile_has_a_gradient(self):
        from ui import tile_variants as tv
        s = tv.build_tile("grass", 0, 48, ss=3)
        top = s.get_at((24, 2))[:3]
        bottom = s.get_at((24, 45))[:3]
        # the directional gradient makes top lighter than bottom
        self.assertNotEqual(top, bottom)

    def test_many_distinct_shades(self):
        from ui import tile_variants as tv
        s = tv.build_tile("grass", 0, 48, ss=3)
        shades = {s.get_at((x, y))[:3]
                  for x in range(0, 48, 3) for y in range(0, 48, 3)}
        # a flat dither had ~3 tones; the layered tile has many more
        self.assertGreater(len(shades), 20, "tile should be richly shaded")


if __name__ == "__main__":
    unittest.main()
