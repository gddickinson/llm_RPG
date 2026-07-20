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

    def test_night_floor_is_playable(self):
        # George 2026-07-15: night was too dark — the floor was lifted so the
        # ground beyond the torch-pool stays dim-but-visible (not pure black).
        self.assertLessEqual(TOD_DARKNESS["night"], 150,
                             "night must not be pitch black")
        self.assertLess(TOD_DARKNESS["evening"], TOD_DARKNESS["night"])

    def test_wider_torch_pool_lights_more(self):
        # a wider radius + gentler falloff → the night frame is brighter than
        # a tight 4.5-tile pool would leave it
        e = GameEngine(llm_provider="heuristic", enable_npc_processes=False)
        e.start_game()
        try:
            e.world.time = (e.world.time // 1440) * 1440 + 22 * 60  # 22:00
            screen = pygame.Surface((640, 480))
            screen.fill((120, 120, 120))       # a lit "terrain" base to darken
            LightingOverlay().apply(screen, pygame.Rect(0, 0, 640, 480), e,
                                    cam_x=e.player.position[0] - 13,
                                    cam_y=e.player.position[1] - 10,
                                    tile_size=24)
            # the lit pool around screen-centre is clearly brighter than a corner
            centre = screen.get_at((320, 240))[:3]
            corner = screen.get_at((10, 10))[:3]
            self.assertGreater(sum(centre), sum(corner))
        finally:
            try:
                e.end_game()
            except Exception:
                pass

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
