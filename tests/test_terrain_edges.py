"""P33.2 — terrain edge-blending + water coastline.

Pure neighbour classification (which seams blend, which water is deep/shallow,
which sides get foam) plus a render smoke over the overlay pass.
"""

import os as _os
import tempfile as _tempfile
_os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
_os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_te_"))

import unittest

from ui import terrain_edges as te


def _grid(rows):
    """A (x,y)->name getter over a list-of-rows of single-char codes."""
    code = {"g": "grass", "w": "water", "r": "road", "f": "forest",
            "b": "building", ".": None}

    def get(x, y):
        if 0 <= y < len(rows) and 0 <= x < len(rows[y]):
            return code[rows[y][x]]
        return None
    return get


class TestBlend(unittest.TestCase):
    def test_differing_land_neighbour_blends_right_and_down(self):
        get = _grid(["gr",
                     "fg"])
        edges = te.blend_edges(get, 0, 0)          # grass; right=road, down=forest
        sides = dict(edges)
        self.assertEqual(sides.get("right"), "road")
        self.assertEqual(sides.get("down"), "forest")

    def test_same_terrain_does_not_blend(self):
        get = _grid(["gg", "gg"])
        self.assertEqual(te.blend_edges(get, 0, 0), [])

    def test_building_and_water_do_not_edge_blend(self):
        get = _grid(["gb", "gw"])
        # grass here, right=building (not blendable), down=water (not blendable)
        self.assertEqual(te.blend_edges(get, 0, 0), [])
        # a building tile itself never blends
        self.assertEqual(te.blend_edges(_grid(["bg"]), 0, 0), [])

    def test_water_is_not_in_the_land_blend_set(self):
        self.assertNotIn("water", te.BLENDABLE)


class TestWater(unittest.TestCase):
    def test_shore_sides_face_land(self):
        get = _grid(["ggg",
                     "gww",
                     "www"])
        # water at (1,1): up=grass, left=grass; down/right=water
        sides = set(te.shore_sides(get, 1, 1))
        self.assertIn("up", sides)
        self.assertIn("left", sides)
        self.assertNotIn("down", sides)

    def test_open_water_has_no_shore(self):
        get = _grid(["www", "www", "www"])
        self.assertEqual(te.shore_sides(get, 1, 1), [])

    def test_depth_deep_vs_shallow(self):
        deep = _grid(["www", "www", "www"])
        self.assertEqual(te.water_depth(deep, 1, 1), "deep")
        shallow = _grid(["wgw", "www", "www"])
        self.assertEqual(te.water_depth(shallow, 1, 1), "shallow")

    def test_depth_none_off_water(self):
        self.assertIsNone(te.water_depth(_grid(["g"]), 0, 0))

    def test_shimmer_frame_bounded_and_deterministic(self):
        self.assertTrue(0 <= te.shimmer_frame(3, 4, 10) < 3)
        self.assertEqual(te.shimmer_frame(3, 4, 10), te.shimmer_frame(3, 4, 10))


class TestRenderSmoke(unittest.TestCase):
    def test_draw_terrain_edges_runs(self):
        import pygame
        pygame.init()
        pygame.display.set_mode((320, 240))
        from engine.game_engine import GameEngine
        from engine.discovery import _explored
        e = GameEngine(llm_provider="heuristic", enable_npc_processes=False)
        e.start_game()
        px, py = e.player.position
        ex = _explored(e)
        for dy in range(-6, 7):
            for dx in range(-6, 7):
                ex.add((px + dx, py + dy))
        surf = pygame.Surface((320, 240))
        view = pygame.Rect(0, 0, 320, 240)
        te.draw_terrain_edges(surf, e, view, max(0, px - 5), max(0, py - 5), 16)
        # cached per tile-size
        self.assertIn(16, te._CACHE)
        e.end_game()


if __name__ == "__main__":
    unittest.main()
