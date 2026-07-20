"""OAKVALE T3 — the defended-core wall + gates (pure, headless)."""

import math
import unittest

from world.town import town_wall as tw
from world.town.streets import plan_streets


class TestPolygon(unittest.TestCase):
    def test_polygon_vertices_near_the_core_ring(self):
        cx, cy, r = 70, 55, 28
        poly = tw.wall_polygon(cx, cy, r, frac=0.5, n=18, seed=1)
        self.assertEqual(len(poly), 18)
        for (x, y) in poly:
            d = math.hypot(x - cx, y - cy)
            self.assertTrue(0.35 * r <= d <= 0.65 * r,
                            "vertices ring the inner core")

    def test_smooth_preserves_count(self):
        poly = [(0, 0), (10, 0), (10, 10), (0, 10)]
        self.assertEqual(len(tw._smooth(poly, 2)), 4)

    def test_wall_tiles_form_a_closed_ring(self):
        poly = tw.wall_polygon(50, 50, 30, seed=2)
        tiles = tw.wall_tiles(poly)
        self.assertGreater(len(tiles), 20)
        # a ring encloses the centre but does not cover it
        self.assertNotIn((50, 50), tiles)


class TestIntersection(unittest.TestCase):
    def test_crossing_segments_intersect(self):
        h = tw._seg_intersect((0, 5), (10, 5), (5, 0), (5, 10))
        self.assertIsNotNone(h)
        self.assertAlmostEqual(h[0], 5, places=5)
        self.assertAlmostEqual(h[1], 5, places=5)

    def test_parallel_segments_dont(self):
        self.assertIsNone(tw._seg_intersect((0, 0), (10, 0), (0, 5), (10, 5)))

    def test_non_touching_dont(self):
        self.assertIsNone(tw._seg_intersect((0, 0), (1, 0), (5, 5), (5, 10)))


class TestGatesAndTowers(unittest.TestCase):
    def setUp(self):
        self.cx, self.cy, self.r = 70, 55, 28
        self.sp = plan_streets(self.cx, self.cy, self.r, size="town", seed=11)
        self.cw = tw.build_core_wall(self.cx, self.cy, self.r, self.sp,
                                     frac=0.5, seed=11)

    def test_multiple_gates_on_the_wall(self):
        self.assertGreaterEqual(len(self.cw.gates), 3, "a wall with many gates")

    def test_gates_lie_on_the_wall_ring(self):
        # every gate is near the polygon ring radius (a real opening in the wall)
        for (gx, gy) in self.cw.gates:
            d = math.hypot(gx - self.cx, gy - self.cy)
            self.assertTrue(0.3 * self.r <= d <= 0.7 * self.r)

    def test_gates_are_gaps_not_wall(self):
        for g in self.cw.gates:
            self.assertNotIn(g, self.cw.wall, "a gate is an opening, not wall")

    def test_towers_present_and_deduped(self):
        self.assertGreaterEqual(len(self.cw.towers), 3)
        for i in range(len(self.cw.towers)):
            for j in range(i + 1, len(self.cw.towers)):
                a, b = self.cw.towers[i], self.cw.towers[j]
                self.assertGreater(abs(a[0] - b[0]) + abs(a[1] - b[1]), 2)

    def test_encloses_core_not_suburbs(self):
        self.assertTrue(self.cw.encloses(self.cx, self.cy),
                        "the centre is inside the defended core")
        self.assertFalse(self.cw.encloses(self.cx, self.cy + int(self.r * 0.9)),
                         "the outer suburbs are outside the wall")

    def test_a_boulevard_passes_through_a_gate(self):
        # a main boulevard tile set includes a tile adjacent to a gate
        mains = [s for s in self.sp.segments if s.kind == "main"]
        road = set()
        for s in mains:
            road.update(s.tiles())
        near = 0
        for (gx, gy) in self.cw.gates:
            if any((gx + dx, gy + dy) in road
                   for dx in (-1, 0, 1) for dy in (-1, 0, 1)):
                near += 1
        self.assertGreater(near, 0, "a boulevard runs through a gate")


if __name__ == "__main__":
    unittest.main()
