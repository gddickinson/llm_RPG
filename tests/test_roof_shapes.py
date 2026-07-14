"""P33.3 — building materials + roof shapes (pure geometry & colour) and the
per-kind style descriptors.
"""

import os as _os
import tempfile as _tempfile
_os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
_os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_rs_"))

import unittest

from ui import roof_shapes as rs


class TestColours(unittest.TestCase):
    def test_covering_and_wall_lookup(self):
        self.assertEqual(rs.covering_color("thatch"), rs.COVERINGS["thatch"])
        self.assertEqual(rs.wall_color("stone"), rs.WALLS["stone"])

    def test_unknown_falls_back(self):
        self.assertEqual(rs.covering_color("mystery"), rs.DEFAULT_COVERING)
        self.assertEqual(rs.wall_color("mystery"), rs.DEFAULT_WALL)

    def test_shades_valid_and_ordered(self):
        sh = rs.roof_shades("clay")
        for key in ("lit", "shadow", "mid", "ridge"):
            self.assertIn(key, sh)
            self.assertTrue(all(0 <= c <= 255 for c in sh[key]))
        self.assertGreater(sum(sh["lit"]), sum(sh["shadow"]))

    def test_front_is_darker_than_wall(self):
        self.assertLess(sum(rs.front_color("timber")),
                        sum(rs.wall_color("timber")))


class TestRoofShapes(unittest.TestCase):
    def test_gable_has_ridge_two_slopes(self):
        g = rs.gable_polys(10, 20, 16, 8)
        self.assertEqual(len(g["polys"]), 2)
        self.assertIsNotNone(g["ridge"])
        self.assertIsNone(g["parapet"])

    def test_hip_has_four_slopes_no_ridge(self):
        hp = rs.hip_polys(10, 20, 16, 8)
        self.assertEqual(len(hp["polys"]), 4)
        self.assertIsNone(hp["ridge"])
        for pts, key in hp["polys"]:
            self.assertEqual(len(pts), 3)          # triangles to the apex

    def test_flat_parapet_toggle(self):
        self.assertIsNone(rs.flat_polys(0, 0, 16, 8, parapet=False)["parapet"])
        self.assertIsNotNone(rs.flat_polys(0, 0, 16, 8, parapet=True)["parapet"])

    def test_roof_polys_dispatch(self):
        self.assertEqual(len(rs.roof_polys("hip", 0, 0, 16, 8)["polys"]), 4)
        self.assertEqual(len(rs.roof_polys("gable", 0, 0, 16, 8)["polys"]), 2)
        self.assertEqual(len(rs.roof_polys("flat", 0, 0, 16, 8)["polys"]), 1)

    def test_chimneys_capped_and_gated(self):
        self.assertEqual(rs.chimney_rects(0, 0, 32, 16, 0), [])
        self.assertEqual(rs.chimney_rects(0, 0, 8, 4, 3), [])   # too small
        self.assertEqual(len(rs.chimney_rects(0, 0, 32, 16, 5)), 2)  # cap 2


class TestStyles(unittest.TestCase):
    def test_load_and_lookup(self):
        from ui.renderer_buildings import load_styles, style_for
        styles = load_styles()
        self.assertIn("temple", styles)
        temple = style_for("temple")
        self.assertEqual(temple["roof"], "hip")
        self.assertEqual(temple["covering"], "slate")

    def test_unknown_kind_is_stone_wall_default(self):
        from ui.renderer_buildings import style_for
        d = style_for("")            # a wall segment / unmapped building
        self.assertEqual(d["roof"], "flat")
        self.assertEqual(d["covering"], "stone")

    def test_every_style_uses_known_materials(self):
        from ui.renderer_buildings import load_styles
        for kind, s in load_styles().items():
            self.assertIn(s["roof"], ("gable", "hip", "flat"), kind)
            self.assertIn(s["covering"], rs.COVERINGS, kind)
            self.assertIn(s["wall"], rs.WALLS, kind)


if __name__ == "__main__":
    unittest.main()
