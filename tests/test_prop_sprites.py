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
        for lit in ("brazier", "wall torch", "candelabra", "iron cauldron"):
            self.assertTrue(ps.emits_light(lit), lit)
        for dark in ("pillar", "sarcophagus", "rug", "statue"):
            self.assertFalse(ps.emits_light(dark), dark)

    def test_scales_to_any_tile_size(self):
        for ts in (16, 32, 48, 64):
            handled, painted = self._nonempty("brazier", ts)
            self.assertTrue(handled and painted, f"brazier at {ts}px")


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
