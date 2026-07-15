"""P39.1 — the decorative prop sprite library (procedural, headless)."""

import os as _os
_os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
_os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import unittest

import pygame

from ui import prop_sprites as ps


class TestProps(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    def _nonempty(self, name, ts=48):
        s = pygame.Surface((ts, ts), pygame.SRCALPHA)
        handled = ps.draw_prop(s, name, ts)
        painted = any(s.get_at((x, y))[3] > 0
                      for x in range(0, ts, 2) for y in range(0, ts, 2))
        return handled, painted

    def test_every_prop_draws_something(self):
        for name in ps.prop_names():
            handled, painted = self._nonempty(name)
            self.assertTrue(handled, f"{name} not handled")
            self.assertTrue(painted, f"{name} drew nothing")

    def test_a_good_variety_of_props(self):
        self.assertGreaterEqual(len(ps.prop_names()), 20,
                                "the world should have many props")

    def test_keyword_matching_is_forgiving(self):
        # a furniture NAME like "Stone Pillar" or "Iron Brazier" still matches
        for name in ("Stone Pillar", "Great Brazier", "Wall Torch",
                     "Ornate Sarcophagus", "Marble Statue"):
            handled, painted = self._nonempty(name)
            self.assertTrue(handled and painted, name)

    def test_unknown_prop_is_not_handled(self):
        s = pygame.Surface((48, 48), pygame.SRCALPHA)
        self.assertFalse(ps.draw_prop(s, "flibbertigibbet", 48))

    def test_lit_props_are_flagged(self):
        for lit in ("brazier", "wall torch", "candelabra", "iron cauldron",
                    "hearth", "forge", "fireplace", "oven"):   # BLD.1 fire pieces
            self.assertTrue(ps.emits_light(lit), lit)
        for dark in ("pillar", "sarcophagus", "rug", "statue"):
            self.assertFalse(ps.emits_light(dark), dark)

    def test_scales_to_any_tile_size(self):
        for ts in (16, 32, 48, 64):
            handled, painted = self._nonempty("brazier", ts)
            self.assertTrue(handled and painted, f"brazier at {ts}px")


class TestRenderProp(unittest.TestCase):
    """P40.3 supersampled + ground-shadowed props."""
    def test_render_prop_returns_sized_sprite(self):
        s = ps.render_prop("pillar", 48, ss=3)
        self.assertIsNotNone(s)
        self.assertEqual(s.get_size(), (48, 48))

    def test_non_prop_is_none(self):
        self.assertIsNone(ps.render_prop("flibbertigibbet", 48))

    def test_ground_prop_gets_a_contact_shadow(self):
        # a floor prop has dark shadow pixels below its base that the bare
        # draw (no shadow) does not
        grounded = ps.render_prop("sarcophagus", 48, ss=2, shadow=True)
        bare = ps.render_prop("sarcophagus", 48, ss=2, shadow=False)
        band = [(x, y) for x in range(14, 34) for y in range(38, 45)]
        g_alpha = sum(grounded.get_at(p)[3] for p in band)
        b_alpha = sum(bare.get_at(p)[3] for p in band)
        self.assertGreater(g_alpha, b_alpha, "shadow adds grounding under it")

    def test_wall_prop_has_no_ground_shadow(self):
        # a wall/ceiling piece is not grounded (tapestry, chandelier)
        grounded = ps.render_prop("tapestry", 48, ss=2, shadow=True)
        bare = ps.render_prop("tapestry", 48, ss=2, shadow=False)
        self.assertEqual(
            pygame.image.tostring(grounded, "RGBA"),
            pygame.image.tostring(bare, "RGBA"),
            "a wall prop should get no ground shadow")


class TestFurnitureDispatch(unittest.TestCase):
    def test_sprite_loader_routes_new_props(self):
        from ui.sprite_loader import SpriteLoader
        sl = SpriteLoader(tile_size=48)
        surf = sl.furniture("Brazier")
        self.assertIsNotNone(surf)
        painted = any(surf.get_at((x, y))[3] > 0
                      for x in range(0, 48, 3) for y in range(0, 48, 3))
        self.assertTrue(painted, "furniture() should draw the brazier")

    def test_legacy_furniture_still_works(self):
        from ui.sprite_loader import SpriteLoader
        sl = SpriteLoader(tile_size=48)
        for legacy in ("Bed", "Chest", "Anvil", "Altar", "Barrel"):
            surf = sl.furniture(legacy)
            self.assertIsNotNone(surf, legacy)


if __name__ == "__main__":
    unittest.main()
