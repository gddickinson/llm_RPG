"""Tileset pipeline tests (P15.1)."""

import os
import shutil
import tempfile
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame


class TestTileset(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((64, 64))
        # a fake tileset with ONE tile: pure magenta grass
        cls.tiles_root = os.path.join(
            os.path.dirname(os.path.dirname(
                os.path.abspath(__file__))), "data", "tiles")
        cls.set_dir = tempfile.mkdtemp(
            prefix="testset_", dir=cls.tiles_root)
        cls.set_name = os.path.basename(cls.set_dir)
        surf = pygame.Surface((16, 16))
        surf.fill((255, 0, 255))
        pygame.image.save(surf,
                          os.path.join(cls.set_dir, "grass.png"))
        ent = os.path.join(cls.set_dir, "entities")
        os.makedirs(ent, exist_ok=True)
        psurf = pygame.Surface((16, 16))
        psurf.fill((0, 255, 0))
        pygame.image.save(psurf, os.path.join(ent, "player.png"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.set_dir, ignore_errors=True)
        os.environ.pop("LLM_RPG_TILESET", None)

    def _loader(self, tileset=None):
        from ui.sprite_loader import SpriteLoader
        if tileset is None:
            os.environ.pop("LLM_RPG_TILESET", None)
        else:
            os.environ["LLM_RPG_TILESET"] = tileset
        return SpriteLoader(tile_size=32)

    def test_default_is_procedural(self):
        loader = self._loader(None)
        self.assertIsNone(loader.tileset_dir)
        tile = loader.tile("grass")
        self.assertNotEqual(tile.get_at((8, 8))[:3], (255, 0, 255))

    def test_tileset_image_wins(self):
        loader = self._loader(self.set_name)
        self.assertIsNotNone(loader.tileset_dir)
        tile = loader.tile("grass")
        self.assertEqual(tile.get_at((8, 8))[:3], (255, 0, 255),
                         "the PNG replaced the procedural grass")
        self.assertEqual(tile.get_size(), (32, 32),
                         "16px source scaled to the tile size")

    def test_missing_images_fall_back(self):
        loader = self._loader(self.set_name)
        tile = loader.tile("water")     # not in the set
        self.assertNotEqual(tile.get_at((8, 8))[:3], (255, 0, 255),
                            "water falls back to procedural")

    def test_entity_override(self):
        loader = self._loader(self.set_name)
        sprite = loader.character("warrior", is_player=True)
        self.assertEqual(sprite.get_at((16, 16))[:3], (0, 255, 0),
                         "the player PNG replaced the drawn body")
        npc = loader.character("guard")
        self.assertNotEqual(npc.get_at((16, 16))[:3], (0, 255, 0),
                            "no guard.png: procedural body")

    def test_unknown_set_name_is_procedural(self):
        loader = self._loader("no_such_set_exists")
        self.assertIsNone(loader.tileset_dir)

    def test_the_bridge_sprite_draws(self):
        """Regression: round 119's bridge sprite had a NameError
        that only fired on first GUI draw."""
        loader = self._loader(None)
        tile = loader.tile("bridge")
        self.assertEqual(tile.get_size(), (32, 32))
        self.assertIs(loader.tile("bridge"), tile, "and it caches")


if __name__ == "__main__":
    unittest.main()
