"""Smoke tests for the lighting and weather visual overlays."""

import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame
pygame.init()


from ui.lighting import LightingOverlay, TOD_DARKNESS
from ui.weather_overlay import WeatherOverlay, PARTICLE_COUNTS
from engine.game_engine import GameEngine


class TestLighting(unittest.TestCase):
    def test_darkness_table(self):
        self.assertEqual(TOD_DARKNESS["afternoon"], 0)
        self.assertGreater(TOD_DARKNESS["night"], 100)

    def test_apply_does_not_crash(self):
        e = GameEngine(llm_provider="heuristic", enable_npc_processes=False)
        e.start_game()
        try:
            screen = pygame.Surface((640, 480))
            view = pygame.Rect(0, 0, 640, 480)
            lo = LightingOverlay()
            # Force night
            e.world.time = 22 * 60   # 22:00
            lo.apply(screen, view, e, cam_x=0, cam_y=0, tile_size=24)
        finally:
            try:
                e.end_game()
            except Exception:
                pass


class TestWeatherOverlay(unittest.TestCase):
    def test_particle_counts(self):
        self.assertEqual(PARTICLE_COUNTS["clear"], 0)
        self.assertGreater(PARTICLE_COUNTS["rain"], 0)
        self.assertGreater(PARTICLE_COUNTS["snow"], 0)

    def test_update_and_draw_smoke(self):
        view = pygame.Rect(0, 0, 320, 240)
        screen = pygame.Surface(view.size)
        wo = WeatherOverlay()
        for kind in ("clear", "rain", "snow", "fog", "storm"):
            wo.update(0.1, kind, view)
            wo.draw(screen, view)
            # rain/snow/fog/storm should populate particles or fog surf
            if kind == "clear":
                self.assertEqual(len(wo.particles), 0)
            elif kind != "fog":
                self.assertGreater(len(wo.particles), 0)


if __name__ == "__main__":
    unittest.main()
