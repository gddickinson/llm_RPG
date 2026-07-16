"""OAKVALE T2 — the town street network (pure, headless)."""

import math
import unittest

from world.town import streets
from world.town.streets import plan_streets, StreetPlan


class TestPrimitives(unittest.TestCase):
    def test_bresenham_endpoints_and_contiguity(self):
        ts = streets._line_tiles(0, 0, 5, 3)
        self.assertEqual(ts[0], (0, 0))
        self.assertEqual(ts[-1], (5, 3))
        # each step moves at most one tile in x and y (contiguous)
        for (a, b) in zip(ts, ts[1:]):
            self.assertLessEqual(abs(a[0] - b[0]), 1)
            self.assertLessEqual(abs(a[1] - b[1]), 1)

    def test_thicken_widens(self):
        line = [(5, 5), (6, 5)]
        wide = streets._thicken(line, 1)
        self.assertGreater(len(wide), len(line))
        self.assertIn((5, 4), wide)     # a tile above the line
        self.assertIn((5, 6), wide)     # and below

    def test_ngon_points_on_circle(self):
        pts = streets._ngon(10, 10, 5, 8)
        self.assertEqual(len(pts), 8)
        for (x, y) in pts:
            self.assertAlmostEqual(math.hypot(x - 10, y - 10), 5, places=5)


class TestPlan(unittest.TestCase):
    def test_boulevards_cross_the_centre_with_a_plaza(self):
        sp = plan_streets(70, 55, 28, size="town", seed=11)
        rt = sp.road_tiles()
        self.assertEqual(rt.get((70, 55)), "plaza", "a market square at centre")
        # at least two 'main' boulevards
        mains = [s for s in sp.segments if s.kind == "main"]
        self.assertGreaterEqual(len(mains), 2)

    def test_town_has_a_ring_road(self):
        sp = plan_streets(70, 55, 28, size="town", seed=3)
        self.assertTrue(any(s.kind == "ring" for s in sp.segments),
                        "a town has a ring road")

    def test_road_tiles_clipped_to_disc(self):
        cx, cy, r = 70, 55, 28
        sp = plan_streets(cx, cy, r, size="town", seed=5)
        for (x, y) in sp.road_tiles():
            self.assertLessEqual((x - cx) ** 2 + (y - cy) ** 2, r * r + 1)

    def test_denser_road_wins_on_shared_tile(self):
        # the plaza (rank 4) overrides any street tile at the very centre
        sp = plan_streets(40, 40, 20, size="town", seed=1)
        self.assertEqual(sp.road_tiles().get((40, 40)), "plaza")

    def test_square_tiles_form_a_disc(self):
        sp = plan_streets(40, 40, 20, size="town", seed=1)
        sq = sp.square_tiles()
        self.assertIn((40, 40), sq)
        for (x, y) in sq:
            self.assertLessEqual(math.hypot(x - 40, y - 40), sp.square_r + 0.5)

    def test_deterministic(self):
        a = plan_streets(70, 55, 28, size="town", seed=9).road_tiles()
        b = plan_streets(70, 55, 28, size="town", seed=9).road_tiles()
        self.assertEqual(a, b)

    def test_village_has_no_ring_but_has_boulevards(self):
        sp = plan_streets(30, 30, 12, size="village", seed=2)
        kinds = {s.kind for s in sp.segments}
        self.assertIn("main", kinds)
        self.assertNotIn("ring", kinds, "a small village skips the ring road")

    def test_network_reaches_from_core_to_edge(self):
        # a radial/boulevard should place road tiles near the disc edge
        cx, cy, r = 70, 55, 28
        rt = plan_streets(cx, cy, r, size="town", seed=7).road_tiles()
        edge = [xy for xy in rt
                if math.hypot(xy[0] - cx, xy[1] - cy) >= r * 0.85]
        self.assertTrue(edge, "streets reach the town edge (gates will meet them)")


if __name__ == "__main__":
    unittest.main()
