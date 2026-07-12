"""Light & weather colour (P15.4): sources, aurora, winter chill."""

import os as _os
import tempfile as _tempfile
import unittest

_os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
_os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_lib_"))

from ui.light_palette import (light_color, night_factor, sky_tint,
                              LIGHT_COLORS, AURORA, WINTER_CHILL,
                              DEFAULT_LIGHT)                # noqa: E402


class TestLightColor(unittest.TestCase):
    def test_named_sources(self):
        self.assertEqual(light_color("wisp"), LIGHT_COLORS["wisp"])
        self.assertEqual(light_color("forge"), LIGHT_COLORS["forge"])

    def test_unknown_source_default(self):
        self.assertEqual(light_color("nope"), DEFAULT_LIGHT)

    def test_all_valid_rgb(self):
        for col in LIGHT_COLORS.values():
            self.assertEqual(len(col), 3)
            self.assertTrue(all(0 <= c <= 255 for c in col))


class TestNightFactor(unittest.TestCase):
    def test_noon_is_zero_deep_night_is_one(self):
        self.assertEqual(night_factor(12.0), 0.0)
        self.assertAlmostEqual(night_factor(2.0), 1.0, places=2)

    def test_bounded(self):
        for h in range(0, 24):
            self.assertTrue(0.0 <= night_factor(h) <= 1.0)


class TestSkyTint(unittest.TestCase):
    def test_aurora_on_clear_conjunction_night(self):
        c = sky_tint(2.0, conjunction=True, weather="clear")
        self.assertEqual(c[:3], AURORA)
        self.assertGreater(c[3], 0)

    def test_no_aurora_by_day(self):
        self.assertEqual(sky_tint(12.0, conjunction=True,
                                  weather="clear")[3], 0)

    def test_no_aurora_through_cloud(self):
        # a conjunction you can't see: overcast blocks it
        self.assertEqual(sky_tint(2.0, conjunction=True,
                                  weather="fog")[3], 0)

    def test_snow_tints_even_by_day(self):
        c = sky_tint(12.0, weather="snow")
        self.assertEqual(c[:3], WINTER_CHILL)
        self.assertGreater(c[3], 0)

    def test_snow_is_stronger_at_night(self):
        day = sky_tint(12.0, weather="snow")[3]
        night = sky_tint(2.0, weather="snow")[3]
        self.assertGreater(night, day)

    def test_winter_night_chill(self):
        c = sky_tint(2.0, weather="clear", season="winter")
        self.assertEqual(c[:3], WINTER_CHILL)
        self.assertGreater(c[3], 0)

    def test_clear_summer_night_is_untinted(self):
        self.assertEqual(sky_tint(2.0, conjunction=False,
                                  weather="clear", season="summer"),
                         (0, 0, 0, 0))

    def test_every_tint_is_valid_rgba(self):
        cases = [
            sky_tint(2.0, conjunction=True, weather="clear"),
            sky_tint(12.0, weather="snow"),
            sky_tint(2.0, weather="clear", season="winter"),
            sky_tint(2.0, weather="clear"),
        ]
        for c in cases:
            self.assertEqual(len(c), 4)
            self.assertTrue(all(0 <= ch <= 255 for ch in c))


class TestLightingWiring(unittest.TestCase):
    def test_apply_runs_with_a_wisp_and_snow(self):
        import pygame
        pygame.init()
        pygame.display.set_mode((320, 240))
        from engine.game_engine import GameEngine
        from ui.lighting import LightingOverlay
        from world.weather import Weather
        from world.monsters import build_monster
        e = GameEngine(llm_provider="heuristic", enable_npc_processes=False)
        e.start_game()
        e.world.time = 22 * 60                    # night
        e.weather_system.state.current = Weather.SNOW
        px, py = e.player.position
        wisp = build_monster("marsh_wisp", (px + 2, py))
        e.npc_manager.add_npc(wisp)
        screen = pygame.Surface((320, 240))
        view = pygame.Rect(0, 0, 320, 240)
        LightingOverlay().apply(screen, view, e, cam_x=0, cam_y=0,
                                tile_size=16)     # must not raise
        e.end_game()


if __name__ == "__main__":
    unittest.main()
