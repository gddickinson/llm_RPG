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

    def test_building_mesh_is_walls_roof_and_more(self):
        # ISO.1: a rich building mesh (walls + windows + door + roof), now in
        # ui.iso_buildings
        from ui import iso_buildings as ib
        meshes = ib.building_mesh("home")
        self.assertGreater(len(meshes), 2)             # more than a box + roof
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

    def test_building_footprints_found(self):
        # ISO.15: enterable buildings expose a full footprint rect + kind
        from ui import iso_structures
        infos = iso_structures.building_infos(self.engine)
        self.assertTrue(infos, "the world's buildings should have footprints")
        wm = self.engine.world.map
        for x0, y0, x1, y1, kind, *_ in infos:
            self.assertIsInstance(kind, str)
            self.assertTrue(0 <= x0 <= x1 < wm.width)
            self.assertTrue(0 <= y0 <= y1 < wm.height)

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
