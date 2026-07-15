"""P39.5 — stair / window / door variants (procedural, headless)."""

import os as _os
_os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
_os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import unittest

import pygame

from ui import openings as op


def _painted(surf, ts=None):
    ts = ts or surf.get_width()
    return any(surf.get_at((x, y))[3] > 0
               for x in range(0, surf.get_width(), 2)
               for y in range(0, surf.get_height(), 2))


class TestStairs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    def test_each_kind_draws_and_caches(self):
        for kind in op.STAIR_KINDS:
            s = op.draw_stairs(48, kind)
            self.assertTrue(_painted(s), kind)
            self.assertIs(op.draw_stairs(48, kind), s)      # cached

    def test_kinds_differ(self):
        wood = op.draw_stairs(48, "wood")
        spiral = op.draw_stairs(48, "spiral")
        diff = any(wood.get_at((x, y)) != spiral.get_at((x, y))
                   for x in range(0, 48, 3) for y in range(0, 48, 3))
        self.assertTrue(diff, "spiral should look different from wooden")

    def test_stair_kind_for_theme(self):
        self.assertEqual(op.stair_kind_for({"stair": "spiral"}), "spiral")
        self.assertEqual(op.stair_kind_for({}), "wood")


class TestWindows(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    def test_shape_for_kind(self):
        self.assertEqual(op.window_shape_for("temple"), "lancet")
        self.assertEqual(op.window_shape_for("wall_tower"), "arrow_loop")
        self.assertEqual(op.window_shape_for("cottage"), "square")

    def test_every_shape_draws(self):
        for shape in ("square", "arched", "lancet", "rose", "round",
                      "arrow_loop"):
            surf = pygame.Surface((40, 40), pygame.SRCALPHA)
            op.draw_window(surf, (12, 18, 12, 12), shape)
            self.assertTrue(_painted(surf), shape)


class TestThemesHaveStairs(unittest.TestCase):
    def test_data_matches_kinds(self):
        import json
        with open("data/interior_themes.json") as fp:
            themes = json.load(fp)["themes"]
        for tid, spec in themes.items():
            kind = spec.get("stair", "wood")
            self.assertIn(kind, op.STAIR_KINDS, f"{tid}: {kind}")


if __name__ == "__main__":
    unittest.main()
