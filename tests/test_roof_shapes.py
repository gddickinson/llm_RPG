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


class TestSpanRoofs(unittest.TestCase):
    """P37.4 — one roof SPANNING a W×D footprint, not a grid of tile roofs."""

    def test_span_faces_cover_the_footprint(self):
        f = rs.span_faces(100, 200, 96, 64, 20)   # a 3x2 building at ts=32
        top, front = f["top"], f["front"]
        self.assertEqual(min(p[0] for p in top), 100)
        self.assertEqual(max(p[0] for p in top), 196)          # px + w
        # the front wall sits below the roof, full width, `h` tall
        self.assertEqual(min(p[0] for p in front), 100)
        self.assertEqual(max(p[0] for p in front), 196)
        ys = sorted(p[1] for p in front)
        self.assertEqual(ys[-1] - ys[0], 20)                    # h pixels tall

    def test_span_gable_ridge_spans_full_width(self):
        g = rs.span_roof("gable", 0, 0, 120, 60, 24)
        self.assertEqual(len(g["polys"]), 2)
        (rl, rr) = g["ridge"]
        self.assertEqual(rl[0], 0)
        self.assertEqual(rr[0], 120)                            # ridge = width

    def test_span_hip_has_a_ridge_line_not_a_point(self):
        hp = rs.span_roof("hip", 0, 0, 120, 60, 24)
        self.assertEqual(len(hp["polys"]), 4)
        rl, rr = hp["ridge"]
        self.assertLess(rl[0], rr[0])              # a real ridge segment
        self.assertGreater(rl[0], 0)               # inset from the eaves
        self.assertLess(rr[0], 120)

    def test_span_flat_parapet_toggle(self):
        self.assertIsNone(rs.span_roof("flat", 0, 0, 64, 64, 16)["parapet"])
        self.assertIsNotNone(
            rs.span_roof("flat", 0, 0, 64, 64, 16, parapet=True)["parapet"])

    def test_span_chimneys_scale_and_cap(self):
        self.assertEqual(rs.span_chimneys(0, 0, 8, 4, 2), [])       # too small
        self.assertEqual(len(rs.span_chimneys(0, 0, 128, 20, 5)), 2)  # cap 2


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


class TestMaterialCoursing(unittest.TestCase):
    """P40.4 wall coursing + roof tile rows — flat faces read as material."""
    QUAD = [(10, 20), (58, 20), (58, 68), (10, 68)]     # a front-wall rect

    def test_masonry_wall_has_courses_and_joints(self):
        segs = rs.wall_courses(self.QUAD, "brick", 48)
        # both horizontal courses and vertical joints appear
        horiz = [s for s in segs if s[1][1] == s[2][1]]
        vert = [s for s in segs if s[1][0] == s[2][0]]
        self.assertTrue(horiz, "brick has horizontal courses")
        self.assertTrue(vert, "brick has staggered vertical joints")

    def test_running_bond_is_staggered(self):
        # adjacent course rows offset their joints (not a stacked grid)
        segs = rs.wall_courses(self.QUAD, "stone", 48)
        vert_x = sorted({s[1][0] for s in segs if s[1][0] == s[2][0]})
        self.assertGreater(len(vert_x), 2, "several joint columns")

    def test_timber_frames_not_bricks(self):
        segs = rs.wall_courses(self.QUAD, "timber", 48)
        # timber is a few framing beams, far fewer than brick courses
        self.assertLess(len(segs), len(rs.wall_courses(self.QUAD, "brick", 48)))

    def test_roof_courses_follow_the_face(self):
        quad = [(10, 0), (58, 0), (58, 24), (10, 24)]
        rows = rs.roof_courses(quad, "slate", 48)
        self.assertTrue(rows, "a roof face gets tile rows")
        # rows span the face width and are darker than the covering
        for _col, a, b in rows:
            self.assertLess(a[0], b[0])
        self.assertLess(sum(rows[0][0]), sum(rs.covering_color("slate")))

    def test_tiny_face_is_safe(self):
        self.assertEqual(rs.roof_courses([(0, 0), (1, 0)], "slate", 48), [])


if __name__ == "__main__":
    unittest.main()
