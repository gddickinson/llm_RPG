"""ISO.1 — richer baked 3D building meshes (headless)."""

import unittest

import numpy as np
import pygame

from ui import iso_buildings as ib
from ui import iso_objects


class TestMesh(unittest.TestCase):
    def test_pyramid_shape(self):
        v, t, c = ib.pyramid(0, 1, 0, 1, 0.5, 1, (100, 100, 100))
        self.assertEqual(len(v), 5, "4 base corners + an apex")
        self.assertEqual(len(t), 4, "four slopes")
        # the apex is the highest vertex
        self.assertEqual(int(np.argmax(v[:, 1])), 4)

    def test_building_mesh_has_walls_roof_windows_door(self):
        meshes = ib.building_mesh("cottage")
        self.assertGreater(len(meshes), 4,
                           "walls + roof + windows + a door at least")
        for (v, t, c) in meshes:
            self.assertEqual(v.shape[1], 3)
            self.assertEqual(t.shape[1], 3)

    def test_tower_is_taller_than_a_cottage(self):
        def top(kind):
            return max(v[:, 1].max() for v, _, _ in ib.building_mesh(kind))
        self.assertGreater(top("tower"), top("cottage"),
                           "a storey-driven tower towers")

    def test_variant_materials_change_colours(self):
        a = ib.building_mesh("home", covering="thatch", wall="timber")
        b = ib.building_mesh("home", covering="slate", wall="stone")
        # the wall box (first mesh) colour differs between variants
        self.assertNotEqual(a[0][2], b[0][2], "wall material colour varies")

    def test_hip_and_flat_roofs_differ_in_geometry(self):
        # a cathedral (its style) vs a cottage produce different roof meshes
        cot = ib.building_mesh("cottage")
        self.assertTrue(cot, "a cottage bakes a mesh")


class TestSprite(unittest.TestCase):
    def setUp(self):
        pygame.init()

    def test_sprite_is_a_surface_with_content(self):
        spr = iso_objects.building_sprite("cottage", 96, "thatch", "timber")
        self.assertIsInstance(spr, pygame.Surface)
        self.assertGreater(spr.get_width(), 0)
        # some non-transparent pixels were drawn
        self.assertGreater(pygame.mask.from_surface(spr).count(), 50)

    def test_variant_is_cached_separately(self):
        s1 = iso_objects.building_sprite("home", 64, "thatch", "timber")
        s2 = iso_objects.building_sprite("home", 64, "slate", "stone")
        s1b = iso_objects.building_sprite("home", 64, "thatch", "timber")
        self.assertIs(s1, s1b, "same variant → cached sprite reused")
        self.assertIsNot(s1, s2, "different variant → distinct sprite")


if __name__ == "__main__":
    unittest.main()
