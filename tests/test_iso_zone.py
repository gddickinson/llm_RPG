"""P41.6 — isometric interior / dungeon render (headless)."""

import os as _os
_os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
_os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
import tempfile as _tempfile
_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_isoz_"))

import unittest

import pygame

from ui import iso_zone


class TestIsoZone(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        cls._flag = _os.environ.pop("LLM_RPG_NO_ADVENTURERS", None)
        from engine.game_engine import GameEngine
        cls.engine = GameEngine(llm_provider="heuristic",
                                enable_npc_processes=False)
        cls.engine.start_game()
        e = cls.engine
        vpos = e.adventure_tome.area_pos("drowned_vault")
        e.world.map.remove_character(e.player)
        e.player.position = tuple(vpos)
        e.world.map.place_character(e.player, *vpos)
        e.enter_building()
        cls.zone = e.current_interior

    @classmethod
    def tearDownClass(cls):
        try:
            cls.engine.end_game()
        except Exception:
            pass
        if cls._flag is not None:
            _os.environ["LLM_RPG_NO_ADVENTURERS"] = cls._flag

    def _render(self):
        from ui.sprite_loader import SpriteLoader
        surf = pygame.Surface((640, 480))
        surf.fill((0, 0, 0))
        iso_zone.render_zone_iso(surf, self.engine,
                                 pygame.Rect(0, 0, 640, 480), self.zone, 48,
                                 SpriteLoader(tile_size=48))
        return surf

    def test_the_crypt_is_a_real_zone(self):
        self.assertEqual(getattr(self.zone, "structure_id", None),
                         "drowned_vault")

    def test_iso_interior_paints(self):
        surf = self._render()
        painted = sum(1 for x in range(0, 640, 12) for y in range(0, 480, 12)
                      if surf.get_at((x, y))[:3] != (0, 0, 0))
        self.assertGreater(painted, 40, "the iso crypt should fill the view")

    def test_zone_chars_include_the_hero(self):
        chars = iso_zone._zone_chars(self.engine, self.zone)
        ids = [c.id for c, _ in chars]
        self.assertIn(self.engine.player.id, ids)

    def test_dispatch_routes_a_zone_to_iso_when_enabled(self):
        _os.environ["LLM_RPG_RENDER"] = "iso"
        try:
            from ui.renderer import MapRenderer
            from ui import iso_render
            r = MapRenderer(tile_size=48)
            surf = pygame.Surface((640, 480))
            surf.fill((0, 0, 0))
            handled = iso_render.dispatch(r, surf, self.engine,
                                          pygame.Rect(0, 0, 640, 480),
                                          self.zone)
            self.assertTrue(handled)
        finally:
            _os.environ.pop("LLM_RPG_RENDER", None)

    def test_dispatch_declines_when_off(self):
        _os.environ.pop("LLM_RPG_RENDER", None)
        from ui.renderer import MapRenderer
        from ui import iso_render
        r = MapRenderer(tile_size=48)
        surf = pygame.Surface((64, 64))
        self.assertFalse(iso_render.dispatch(r, surf, self.engine,
                                             pygame.Rect(0, 0, 64, 64),
                                             self.zone))


if __name__ == "__main__":
    unittest.main()
