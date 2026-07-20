"""ISO.2 — textured iso ground diamonds (headless)."""

import unittest

import pygame

from ui import iso_tiles


class TestIsoTiles(unittest.TestCase):
    def setUp(self):
        pygame.init()

    def test_base_name_strips_variant_digit(self):
        self.assertEqual(iso_tiles._base_name("grass2"), "grass")
        self.assertEqual(iso_tiles._base_name("water"), "water")

    def test_textured_terrain_returns_a_diamond_surface(self):
        s = iso_tiles.tile_diamond("grass", 3, 4, 48, 24)
        self.assertIsInstance(s, pygame.Surface)
        self.assertEqual(s.get_size(), (48, 24))
        # centre opaque, corners clipped away (a diamond)
        self.assertGreater(s.get_at((24, 12))[3], 0, "centre is drawn")
        self.assertEqual(s.get_at((1, 1))[3], 0, "a corner is clipped")

    def test_unknown_terrain_is_none(self):
        self.assertIsNone(iso_tiles.tile_diamond("void", 1, 1, 48, 24))

    def test_cached_and_deterministic(self):
        a = iso_tiles.tile_diamond("grass", 5, 5, 48, 24)
        b = iso_tiles.tile_diamond("grass", 5, 5, 48, 24)
        self.assertIs(a, b, "same tile → cached surface reused")


if __name__ == "__main__":
    unittest.main()
