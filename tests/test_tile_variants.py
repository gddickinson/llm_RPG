"""P33.1 — per-tile variety + texture (kill the graph-paper grid).

The pure hash/dither/scatter math, the recipe table, and the SpriteLoader
integration that picks a textured variant by world position.
"""

import os as _os
import tempfile as _tempfile
_os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
_os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_tv_"))

import unittest

from ui import tile_variants as tv


class TestVariantHash(unittest.TestCase):
    def test_in_range(self):
        for wx in range(-5, 30):
            for wy in range(-5, 30):
                v = tv.variant_index(wx, wy, "grass")
                self.assertTrue(0 <= v < tv.N_VARIANTS)

    def test_deterministic(self):
        self.assertEqual(tv.variant_index(7, 9, "forest"),
                         tv.variant_index(7, 9, "forest"))

    def test_horizontal_and_vertical_neighbours_differ(self):
        # the hash steps 7 (x) and 13 (y); for N=4 both are coprime-ish to 4
        # so an adjacent tile ALWAYS lands on a different variant
        for wx in range(0, 12):
            for wy in range(0, 12):
                v = tv.variant_index(wx, wy, "grass")
                self.assertNotEqual(v, tv.variant_index(wx + 1, wy, "grass"))
                self.assertNotEqual(v, tv.variant_index(wx, wy + 1, "grass"))

    def test_type_id_stable_and_bounded(self):
        self.assertEqual(tv.type_id("water"), tv.type_id("water"))
        self.assertTrue(0 <= tv.type_id("water") < 97)


class TestDither(unittest.TestCase):
    def test_grid_shape_and_range(self):
        g = tv.dither_grid(16, 42, [3, 2, 1])
        self.assertEqual(len(g), 16)
        self.assertEqual(len(g[0]), 16)
        for row in g:
            for cell in row:
                self.assertTrue(0 <= cell < 3)

    def test_grid_deterministic(self):
        self.assertEqual(tv.dither_grid(12, 5, [1, 1]),
                         tv.dither_grid(12, 5, [1, 1]))

    def test_different_seeds_differ(self):
        self.assertNotEqual(tv.dither_grid(16, 1, [1, 1, 1]),
                            tv.dither_grid(16, 2, [1, 1, 1]))

    def test_scatter_bounds_and_count(self):
        pts = tv.scatter_points(20, 6, 3, margin=2)
        self.assertEqual(len(pts), 6)
        for (x, y) in pts:
            self.assertTrue(2 <= x <= 17 and 2 <= y <= 17)

    def test_scatter_deterministic(self):
        self.assertEqual(tv.scatter_points(20, 5, 9),
                         tv.scatter_points(20, 5, 9))


class TestRecipes(unittest.TestCase):
    def test_core_terrains_present(self):
        for t in ("grass", "forest", "water", "mountain", "swamp", "road"):
            self.assertIn(t, tv.RECIPES)

    def test_recipes_well_formed(self):
        for name, r in tv.RECIPES.items():
            self.assertTrue(r["shades"], name)
            for (rgb, w) in r["shades"]:
                self.assertEqual(len(rgb), 3)
                self.assertTrue(all(0 <= c <= 255 for c in rgb), name)
                self.assertGreater(w, 0)
            self.assertIn("kind", r["detail"])


class TestBuild(unittest.TestCase):
    def test_build_returns_sized_surface(self):
        import pygame
        pygame.init()
        s = tv.build_tile("grass", 0, 32)
        self.assertIsNotNone(s)
        self.assertEqual(s.get_size(), (32, 32))

    def test_variants_differ(self):
        import pygame
        pygame.init()
        a = tv.build_tile("grass", 0, 32)
        b = tv.build_tile("grass", 2, 32)
        # different variant seeds → different pixels somewhere
        self.assertNotEqual(pygame.image.tostring(a, "RGB"),
                            pygame.image.tostring(b, "RGB"))

    def test_non_recipe_returns_none(self):
        self.assertIsNone(tv.build_tile("building", 0, 32))
        self.assertIsNone(tv.build_tile("cave", 0, 32))


class TestLoaderIntegration(unittest.TestCase):
    def setUp(self):
        import pygame
        pygame.init()
        pygame.display.set_mode((64, 64))
        from ui.sprite_loader import SpriteLoader
        self.sl = SpriteLoader(tile_size=32)

    def test_same_position_same_surface(self):
        a = self.sl.tile_variant("grass", 5, 5)
        b = self.sl.tile_variant("grass", 5, 5)
        self.assertIs(a, b)                       # cached

    def test_neighbour_tiles_use_different_variants(self):
        import pygame
        a = self.sl.tile_variant("grass", 5, 5)
        b = self.sl.tile_variant("grass", 6, 5)   # adjacent → other variant
        self.assertNotEqual(pygame.image.tostring(a, "RGB"),
                            pygame.image.tostring(b, "RGB"))

    def test_non_recipe_terrain_falls_back(self):
        # building has no recipe → the classic single stamp path
        a = self.sl.tile_variant("building", 1, 1)
        self.assertIs(a, self.sl.tile("building"))

    def test_smooth_off_uses_the_classic_flat_tile(self):
        # ESCAPE HATCH: "Smooth sprites" off (SSAA<=1) → known-good flat tile,
        # no gfx/smoothscale path (George's "ground tiles are mainly black")
        self.sl._variant_cache.clear()
        tv.SSAA = 1
        try:
            self.assertIs(self.sl.tile_variant("grass", 5, 5),
                          self.sl.tile("grass"))
        finally:
            tv.SSAA = None

    def test_built_tiles_are_32bit(self):
        # 32-bit source is what makes smoothscale safe on any display
        s = tv.build_tile("grass", 0, 32, ss=3)
        self.assertGreaterEqual(s.get_bitsize(), 24)

    def test_broken_dark_tile_falls_back(self):
        from ui.sprite_loader import _looks_broken
        import pygame
        black = pygame.Surface((32, 32))
        black.fill((0, 0, 0))
        self.assertTrue(_looks_broken(black, self.sl.tile("grass")))
        # a normal built tile is NOT flagged
        good = tv.build_tile("grass", 0, 32, ss=3)
        self.assertFalse(_looks_broken(good, self.sl.tile("grass")))


if __name__ == "__main__":
    unittest.main()
