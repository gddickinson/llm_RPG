"""P41.4 — baked 3D object sprites for the iso world (headless)."""

import os as _os
_os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
_os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import unittest

import pygame

from ui import iso_objects as io


def _painted(spr):
    w, h = spr.get_size()
    return sum(1 for x in range(0, w, 3) for y in range(0, h, 3)
               if spr.get_at((x, y))[3] > 0)


class TestBakedSprites(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    def test_building_sprites_bake_per_kind(self):
        for kind in ("home", "temple", "tower", "forge", "wall_tower"):
            spr = io.building_sprite(kind, 64)
            self.assertEqual(spr.get_size(), (64, 64))
            self.assertGreater(_painted(spr), 30, kind)

    def test_tree_and_rock_bake(self):
        self.assertGreater(_painted(io.tree_sprite(64)), 20)
        self.assertGreater(_painted(io.rock_sprite(64)), 15)

    def test_sprites_are_cached(self):
        self.assertIs(io.building_sprite("home", 48),
                      io.building_sprite("home", 48))
        self.assertIs(io.tree_sprite(48), io.tree_sprite(48))

    def test_building_mesh_is_walls_plus_roof(self):
        meshes = io._building_mesh("home")
        self.assertEqual(len(meshes), 2)               # a box + a roof
        for verts, tris, color in meshes:
            self.assertEqual(verts.shape[1], 3)
            self.assertEqual(tris.shape[1], 3)


class TestPlacement(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        import tempfile
        _os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                               tempfile.mkdtemp(prefix="llmrpg_isoo_"))
        from engine.game_engine import GameEngine
        cls.engine = GameEngine(llm_provider="heuristic",
                                enable_npc_processes=False)
        cls.engine.start_game()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.engine.end_game()
        except Exception:
            pass

    def test_building_anchors_found(self):
        from ui.iso_render import _building_anchors
        anchors = _building_anchors(self.engine)
        self.assertTrue(anchors, "the town's buildings should have anchors")
        # each anchor names a kind and sits at a real tile
        for (wx, wy), kind in anchors.items():
            self.assertIsInstance(kind, str)
            self.assertTrue(0 <= wx < self.engine.world.map.width)

    def test_iso_frame_with_objects_paints(self):
        from ui import iso_render
        surf = pygame.Surface((640, 480))
        surf.fill((0, 0, 0))
        iso_render.render_iso(surf, self.engine,
                              pygame.Rect(0, 0, 640, 480), 48)
        painted = sum(1 for x in range(0, 640, 12) for y in range(0, 480, 12)
                      if surf.get_at((x, y))[:3] != (0, 0, 0))
        self.assertGreater(painted, 40)


if __name__ == "__main__":
    unittest.main()
