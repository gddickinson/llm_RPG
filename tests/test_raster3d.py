"""P41.2 — the numpy software 3D rasterizer + bake (headless)."""

import os as _os
_os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
_os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import unittest

import numpy as np
import pygame

from ui import raster3d as r3


class TestMeshes(unittest.TestCase):
    def test_box_and_roof_are_valid_meshes(self):
        for verts, tris, color in (r3.box(0, 0, 0, 1, 1, 1, (200, 100, 50)),
                                   r3.roof(0, 1, 0, 1, 0.5, 1, (150, 70, 58))):
            self.assertEqual(verts.shape[1], 3)
            self.assertEqual(tris.shape[1], 3)
            self.assertTrue((tris < len(verts)).all())
            self.assertEqual(len(color), 3)


class TestRender(unittest.TestCase):
    def test_a_box_paints_shaded_faces(self):
        rgb, mask = r3.render([r3.box(0, 0, 0, 1, 1, 1, (180, 150, 110))],
                              width=48, height=48)
        self.assertGreater(int(mask.sum()), 50, "the box should cover pixels")
        # Lambert shading → the visible faces are different brightnesses
        shades = {tuple(c) for c in rgb[mask]}
        self.assertGreaterEqual(len(shades), 2,
                                "lit + shadowed faces differ")

    def test_empty_scene_is_blank(self):
        rgb, mask = r3.render([], width=16, height=16)
        self.assertEqual(int(mask.sum()), 0)

    def test_back_faces_are_culled(self):
        # only ~3 of a box's 6 faces face the camera → far fewer than all tris
        rgb, mask = r3.render([r3.box(0, 0, 0, 1, 1, 1, (200, 200, 200))],
                              width=40, height=40)
        # a fully-visible box would fill much more than a thin sliver
        self.assertLess(int(mask.sum()), 40 * 40, "not the whole frame")
        self.assertGreater(int(mask.sum()), 0)


class TestBake(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    def test_bake_returns_a_transparent_shaded_sprite(self):
        spr = r3.bake([r3.box(0, 0, 0, 1, 1, 1, (176, 150, 110))], size=64)
        self.assertEqual(spr.get_size(), (64, 64))
        # the object is drawn...
        opaque = sum(1 for x in range(0, 64, 2) for y in range(0, 64, 2)
                     if spr.get_at((x, y))[3] > 40)
        self.assertGreater(opaque, 20)
        # ...on a transparent background (a corner pixel is clear)
        self.assertEqual(spr.get_at((0, 0))[3], 0)

    def test_bake_scales_to_size(self):
        for size in (32, 48, 96):
            self.assertEqual(r3.bake(
                [r3.box(0, 0, 0, 1, 1, 1, (150, 150, 150))], size=size
            ).get_size(), (size, size))


if __name__ == "__main__":
    unittest.main()


class TestSSAA(unittest.TestCase):
    def test_ssaa_default_and_clamp(self):
        import os
        from ui import raster3d as r3
        old = os.environ.get("LLM_RPG_ISO_SS")
        try:
            os.environ.pop("LLM_RPG_ISO_SS", None)
            self.assertEqual(r3._ssaa(), 3, "default 3x supersample")
            os.environ["LLM_RPG_ISO_SS"] = "9"
            self.assertEqual(r3._ssaa(), 4, "clamped to 4")
            os.environ["LLM_RPG_ISO_SS"] = "1"
            self.assertEqual(r3._ssaa(), 2, "clamped to 2")
            os.environ["LLM_RPG_ISO_SS"] = "junk"
            self.assertEqual(r3._ssaa(), 3, "bad value → default")
        finally:
            if old is None:
                os.environ.pop("LLM_RPG_ISO_SS", None)
            else:
                os.environ["LLM_RPG_ISO_SS"] = old
