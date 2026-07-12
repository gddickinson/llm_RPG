"""2.5D building render (P16.5): the pure geometry + colour math."""

import os as _os
import tempfile as _tempfile
import unittest

_os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
_os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_lib_"))

from ui import renderer_buildings as rb                   # noqa: E402


class TestHeight(unittest.TestCase):
    def test_taller_buildings_stand_higher(self):
        ts = 32
        self.assertGreater(rb.height_for("tower", ts),
                           rb.height_for("farmhouse", ts))
        self.assertGreater(rb.height_for("farmhouse", ts),
                           rb.height_for("well", ts))

    def test_unknown_kind_uses_default(self):
        self.assertEqual(rb.height_for("mystery", 32),
                         int(rb.DEFAULT_FRAC * 32))

    def test_minimum_height(self):
        self.assertGreaterEqual(rb.height_for("well", 1), 2)

    def test_scales_with_tile_size(self):
        self.assertGreater(rb.height_for("tower", 48),
                           rb.height_for("tower", 16))


class TestGeometry(unittest.TestCase):
    def test_cube_top_is_lifted(self):
        f = rb.cube_faces(10, 20, 16, 8)
        self.assertEqual(f["top"][0], (10, 12))       # sy - h
        self.assertEqual(len(f["top"]), 4)

    def test_front_wall_reaches_the_base(self):
        f = rb.cube_faces(10, 20, 16, 8)
        self.assertEqual(f["front"][2], (26, 36))     # (sx+ts, sy+ts)
        self.assertEqual(len(f["front"]), 4)

    def test_ridge_splits_the_roof(self):
        r = rb.roof_faces(10, 20, 16, 8)
        ridge_y = r["ridge"][0][1]
        self.assertEqual(ridge_y, 20)                 # midpoint of 12..28
        self.assertLess(r["lit"][0][1], ridge_y)      # lit slope is north
        self.assertGreater(r["shadow"][2][1], ridge_y)  # shadow is south


class TestColours(unittest.TestCase):
    def test_lit_roof_is_brighter_than_shadow(self):
        c = rb.face_colors()
        self.assertGreater(sum(c["roof_lit"]), sum(c["roof_shadow"]))

    def test_front_wall_is_darker(self):
        c = rb.face_colors()
        self.assertLess(sum(c["front"]), sum(c["roof_lit"]))

    def test_all_valid_rgb(self):
        for col in rb.face_colors().values():
            self.assertEqual(len(col), 3)
            self.assertTrue(all(0 <= v <= 255 for v in col))


class TestRenderSmoke(unittest.TestCase):
    def test_draw_buildings_does_not_crash(self):
        import pygame
        pygame.init()
        pygame.display.set_mode((320, 240))
        from engine.game_engine import GameEngine
        from world.world_map import TerrainType
        from engine.discovery import _explored
        e = GameEngine(llm_provider="heuristic", enable_npc_processes=False)
        e.start_game()
        # find a building tile and put the player + fog on it
        wmap = e.world.map
        spot = None
        for y in range(wmap.height):
            for x in range(wmap.width):
                if wmap.terrain[y][x] == TerrainType.BUILDING:
                    spot = (x, y)
                    break
            if spot:
                break
        self.assertIsNotNone(spot)
        e.player.position = spot
        ex = _explored(e)
        for dy in range(-4, 5):
            for dx in range(-4, 5):
                ex.add((spot[0] + dx, spot[1] + dy))
        surf = pygame.Surface((320, 240))
        view = pygame.Rect(0, 0, 320, 240)
        rb.draw_buildings(surf, e, view, max(0, spot[0] - 5),
                          max(0, spot[1] - 5), 16)     # must not raise
        e.end_game()


if __name__ == "__main__":
    unittest.main()
