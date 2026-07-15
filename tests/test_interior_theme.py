"""P39.2 — interior visual themes (palette + mood per zone)."""

import os as _os
_os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
_os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import types
import unittest

import pygame

from ui import interior_theme as it


def _zone(name="", structure_id=None, rooms=False):
    z = types.SimpleNamespace(name=name)
    if structure_id is not None:
        z.structure_id = structure_id
    if rooms:
        z.rooms = []
    return z


class TestThemeFor(unittest.TestCase):
    def _tid(self, theme):
        themes = it._themes()
        return next((k for k, v in themes.items() if v is theme), None)

    def test_keyword_resolution(self):
        cases = {
            "Drowned Vault — Flooded Antechamber": "tomb",
            "Temple of Light — Sanctuary": "temple",
            "Durgan's Forge (interior)": "smithy",
            "Oakvale Tavern (interior)": "tavern",
            "The Grand Library": "library",
            "General Store (interior)": "home",
        }
        for name, want in cases.items():
            self.assertEqual(self._tid(it.theme_for(_zone(name))), want, name)

    def test_dungeon_defaults_to_cave(self):
        self.assertEqual(self._tid(it.theme_for(_zone("", rooms=True))), "cave")

    def test_building_defaults_to_home(self):
        self.assertEqual(self._tid(it.theme_for(_zone("Nondescript Hut"))),
                         "home")

    def test_structure_id_participates(self):
        z = _zone("Level One", structure_id="drowned_vault")
        self.assertEqual(self._tid(it.theme_for(z)), "tomb")


class TestThemeSurfaces(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    def test_fill_is_dark(self):
        tomb = it.theme_for(_zone("Crypt"))
        self.assertTrue(all(c < 40 for c in it.fill_color(tomb)))

    def test_tile_surface_opaque_and_coloured(self):
        for name, kind in (("Crypt", "wall"), ("Cozy Home", "floor")):
            th = it.theme_for(_zone(name))
            surf = it.tile_surface(th, kind, 48)
            self.assertIsNotNone(surf)
            self.assertEqual(surf.get_size(), (48, 48))
            # some pixel is a real colour
            self.assertTrue(any(surf.get_at((x, y))[:3] != (0, 0, 0)
                                for x in range(0, 48, 6)
                                for y in range(0, 48, 6)))

    def test_tomb_floor_is_darker_than_home_floor(self):
        tomb = it.tile_surface(it.theme_for(_zone("Tomb")), "floor", 32)
        home = it.tile_surface(it.theme_for(_zone("Home")), "floor", 32)
        self.assertLess(sum(tomb.get_at((16, 16))[:3]),
                        sum(home.get_at((16, 16))[:3]))

    def test_mood_overlay_is_translucent(self):
        mood = it.mood_overlay(it.theme_for(_zone("Crypt")), 100, 80)
        self.assertIsNotNone(mood)
        self.assertLess(mood.get_at((10, 10))[3], 120)   # faint


if __name__ == "__main__":
    unittest.main()
