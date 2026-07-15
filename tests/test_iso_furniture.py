"""P41.8 — baked 3D furniture for the isometric interiors."""

import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import unittest

import pygame

from ui import iso_furniture


class TestIsoFurniture(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    def test_mapped_pieces_bake_to_a_painted_sprite(self):
        for name in ("Sarcophagus", "Pillar", "Altar", "Brazier", "Table",
                     "Chest", "Barrel", "Gravestone", "Urn", "Pew", "Anvil"):
            spr = iso_furniture.furniture_sprite(name, 72)
            self.assertIsNotNone(spr, f"{name} should bake a 3D sprite")
            painted = sum(
                1 for x in range(0, 72, 4) for y in range(0, 72, 4)
                if spr.get_at((x, y))[3] > 0)
            self.assertGreater(painted, 3,
                               f"{name} should actually draw something 3D")

    def test_unmapped_names_fall_back(self):
        for name in ("Cobweb", "Rug", "Bones", "Tapestry", "", None):
            self.assertIsNone(
                iso_furniture.furniture_sprite(name, 72),
                f"{name!r} should return None so the billboard is used")
            self.assertIsNone(iso_furniture.furniture_mesh(name))

    def test_keyword_matching_is_case_insensitive(self):
        self.assertIsNotNone(iso_furniture.furniture_mesh("a dusty SARCOPHAGUS"))
        self.assertIsNotNone(iso_furniture.furniture_mesh("Stone Pillar"))

    def test_sprites_are_cached(self):
        a = iso_furniture.furniture_sprite("Sarcophagus", 64)
        b = iso_furniture.furniture_sprite("Sarcophagus", 64)
        self.assertIs(a, b, "same (kind,size) should return the cached sprite")

    def test_mesh_is_a_list_of_triangle_meshes(self):
        mesh = iso_furniture.furniture_mesh("Altar")
        self.assertIsInstance(mesh, list)
        self.assertGreaterEqual(len(mesh), 1)
        verts, tris, color = mesh[0]      # (vertices, triangles, colour)
        self.assertEqual(len(color), 3)


if __name__ == "__main__":
    unittest.main()
