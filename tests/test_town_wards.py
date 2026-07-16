"""OAKVALE T1 — Voronoi district wards (pure, headless)."""

import math
import random
import unittest

from world.town import wards
from world.town import plan_districts, DistrictPlan


class TestSeeds(unittest.TestCase):
    def test_sunflower_count_and_within_disc(self):
        rng = random.Random(1)
        pts = wards.sunflower_seeds(50, 50, 20, 22, rng)
        self.assertEqual(len(pts), 22)
        for (x, y) in pts:
            self.assertLessEqual(math.hypot(x - 50, y - 50), 20 + 2,
                                 "seeds sit within (a jitter of) the disc")


class TestVoronoi(unittest.TestCase):
    def test_every_disc_tile_assigned_to_a_valid_ward(self):
        rng = random.Random(2)
        seeds = wards.sunflower_seeds(40, 30, 15, 12, rng)
        wm = wards.assign_wards(40, 30, 15, seeds)
        self.assertTrue(wm)
        for (x, y), wid in wm.items():
            self.assertTrue(0 <= wid < len(seeds))
            self.assertLessEqual(math.hypot(x - 40, y - 30), 15 + 0.5)

    def test_tile_goes_to_its_nearest_seed(self):
        # two seeds; a tile is assigned to whichever is closer
        seeds = [(10.0, 10.0), (30.0, 10.0)]
        wm = wards.assign_wards(20, 10, 12, seeds)
        # a tile near the left seed → ward 0; near the right → ward 1
        self.assertEqual(wm.get((12, 10)), 0)
        self.assertEqual(wm.get((28, 10)), 1)

    def test_lloyd_keeps_seeds_in_disc_and_evens_wards(self):
        rng = random.Random(3)
        seeds = wards.sunflower_seeds(50, 50, 18, 16, rng)
        relaxed = wards.lloyd_relax(50, 50, 18, seeds, iterations=3)
        self.assertEqual(len(relaxed), len(seeds))
        for (x, y) in relaxed:
            self.assertLessEqual(math.hypot(x - 50, y - 50), 18 + 1)

        def spread(ss):
            counts = {}
            for wid in wards.assign_wards(50, 50, 18, ss).values():
                counts[wid] = counts.get(wid, 0) + 1
            vals = list(counts.values())
            return max(vals) - min(vals)
        # relaxation should not make ward sizes wildly MORE uneven
        self.assertLessEqual(spread(relaxed), spread(seeds) + 5)


class TestClassify(unittest.TestCase):
    def test_ring_boundaries(self):
        self.assertEqual(wards._ring_of(0, 20), "inner")
        self.assertEqual(wards._ring_of(19, 20), "outer")
        self.assertEqual(wards._ring_of(11, 20), "middle")

    def test_inner_seeds_get_inner_types(self):
        rings = {"inner": ["market"], "middle": ["craft"], "outer": ["farming"]}
        seeds = [(50.0, 50.0), (50.0, 68.0)]     # centre, far edge
        rng = random.Random(0)
        types = wards.classify_wards(50, 50, 20, seeds, rings, rng)
        self.assertEqual(types[0], "market")     # inner
        self.assertEqual(types[1], "farming")    # outer


class TestPlan(unittest.TestCase):
    def test_plan_is_deterministic(self):
        a = plan_districts(60, 45, 22, seed=7, size="town")
        b = plan_districts(60, 45, 22, seed=7, size="town")
        self.assertEqual(a.ward_map, b.ward_map)
        self.assertEqual(a.ward_types, b.ward_types)

    def test_plan_has_a_civic_core_and_suburbs(self):
        p = plan_districts(60, 45, 24, seed=7, size="town")
        self.assertIsInstance(p, DistrictPlan)
        present = p.types_present()
        # inner-ring civic types AND outer-ring suburb types both appear
        self.assertTrue({"market", "civic", "temple"} & present,
                        "an inner civic/market/temple core")
        self.assertIn("residential", present, "residential suburbs")
        # the very centre is an inner-ring district
        self.assertEqual(p.ring_at(60, 45), "inner")

    def test_type_at_outside_disc_is_none(self):
        p = plan_districts(60, 45, 20, seed=1)
        self.assertIsNone(p.type_at(200, 200))

    def test_tiles_of_type_are_that_type(self):
        p = plan_districts(60, 45, 22, seed=4, size="town")
        for dtype in list(p.types_present())[:3]:
            for (x, y) in p.tiles_of_type(dtype)[:10]:
                self.assertEqual(p.type_at(x, y), dtype)


if __name__ == "__main__":
    unittest.main()
