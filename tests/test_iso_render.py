"""P41.3 — the isometric world render path (behind the toggle)."""

import os as _os
_os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
_os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
import tempfile as _tempfile
_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_iso_"))

import unittest

import pygame

from ui import iso_render


class TestToggle(unittest.TestCase):
    def setUp(self):
        self._prev = _os.environ.get("LLM_RPG_RENDER")

    def tearDown(self):
        if self._prev is None:
            _os.environ.pop("LLM_RPG_RENDER", None)
        else:
            _os.environ["LLM_RPG_RENDER"] = self._prev

    def test_env_toggle(self):
        _os.environ["LLM_RPG_RENDER"] = "iso"
        self.assertTrue(iso_render.iso_enabled())
        _os.environ["LLM_RPG_RENDER"] = "topdown"
        self.assertFalse(iso_render.iso_enabled())
        _os.environ.pop("LLM_RPG_RENDER", None)
        self.assertFalse(iso_render.iso_enabled())


class TestRenderIso(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
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

    def test_iso_frame_draws_without_error_and_paints(self):
        surf = pygame.Surface((640, 480))
        surf.fill((0, 0, 0))
        view = pygame.Rect(0, 0, 640, 480)
        iso_render.render_iso(surf, self.engine, view, 48)
        painted = sum(1 for x in range(0, 640, 12) for y in range(0, 480, 12)
                      if surf.get_at((x, y))[:3] != (0, 0, 0))
        self.assertGreater(painted, 40, "the iso world should fill the view")

    def test_origin_centres_the_player(self):
        view = pygame.Rect(0, 0, 640, 480)
        iso = iso_render._projection(48)
        origin = iso_render._origin(iso, self.engine, view)
        px, py = self.engine.player.position
        z = iso_render._HEIGHT.get(
            iso_render._terrain_name(self.engine.world.map.terrain[py][px]), 0)
        sx, sy = iso.world_to_screen(px, py, z, origin)
        # the player projects to (roughly) the middle of the view
        self.assertAlmostEqual(sx, 320, delta=2)
        self.assertAlmostEqual(sy, 240, delta=2)

    def test_terrain_relief_lifts_mountains_sinks_water(self):
        self.assertGreater(iso_render._HEIGHT["mountain"], 0)
        self.assertLess(iso_render._HEIGHT["water"], 0)

    def test_renderer_setting_toggles_iso(self):        # P41.7 in-game toggle
        from engine import settings
        _os.environ.pop("LLM_RPG_RENDER", None)
        settings.set_setting(self.engine.player, "renderer", "topdown")
        self.assertFalse(iso_render.iso_enabled(self.engine))
        settings.set_setting(self.engine.player, "renderer", "iso")
        self.assertTrue(iso_render.iso_enabled(self.engine))
        settings.set_setting(self.engine.player, "renderer", "topdown")

    def test_env_overrides_the_setting(self):
        from engine import settings
        settings.set_setting(self.engine.player, "renderer", "iso")
        _os.environ["LLM_RPG_RENDER"] = "topdown"
        try:
            self.assertFalse(iso_render.iso_enabled(self.engine))
        finally:
            _os.environ.pop("LLM_RPG_RENDER", None)
            settings.set_setting(self.engine.player, "renderer", "topdown")

    def test_draw_diamond_is_shaded_not_flat(self):        # P41.7 fidelity
        import pygame
        from ui.iso import IsoProjection
        surf = pygame.Surface((128, 128))
        surf.fill((0, 0, 0))
        iso_render.draw_diamond(surf, IsoProjection(64, 32, 16),
                                64, 64, (90, 150, 70), seed=7)
        shades = {surf.get_at((x, y))[:3]
                  for x in range(50, 78, 3) for y in range(54, 74, 3)}
        self.assertGreaterEqual(len(shades), 2, "the tile should be shaded")


if __name__ == "__main__":
    unittest.main()
