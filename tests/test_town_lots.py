"""OAKVALE T4 — building lots + the town-generator orchestrator (headless)."""

import unittest

from world.town import lots as L
from world.town.town_gen import plan_town, TownPlan


class TestLotBasics(unittest.TestCase):
    def test_building_size_known_and_default(self):
        self.assertEqual(L.building_size("cathedral"), (6, 5))
        self.assertEqual(L.building_size("home"), (2, 2))
        self.assertEqual(L.building_size("nonsense"), (2, 2))

    def test_lot_tiles_and_center(self):
        lot = L.BuildingLot(10, 20, 3, 2, "shop", "commercial")
        self.assertEqual(len(lot.tiles()), 6)
        self.assertIn((10, 20), lot.tiles())
        self.assertIn((12, 21), lot.tiles())
        self.assertEqual(lot.center(), (11, 21))


class TestTownPlan(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tp = plan_town(80, 68, 40, size="town", seed=11)

    def test_is_a_rich_town(self):
        self.assertIsInstance(self.tp, TownPlan)
        self.assertGreater(self.tp.building_count(), 80,
                           "a large town is densely built")

    def test_landmarks_all_present(self):
        kinds = self.tp.kind_counts()
        for grand in ("cathedral", "hall", "guildhall", "library", "inn",
                      "tavern", "bank", "temple"):
            self.assertIn(grand, kinds, f"the town has a {grand}")
        self.assertEqual(kinds["cathedral"], 1, "exactly one cathedral")

    def test_no_two_buildings_overlap(self):
        seen = set()
        for lot in self.tp.lots:
            for t in lot.tiles():
                self.assertNotIn(t, seen, f"overlap at {t} ({lot})")
                seen.add(t)

    def test_no_building_on_street_plaza_or_wall(self):
        roads = set(self.tp.streets.road_tiles().keys())
        roads |= set(self.tp.streets.square_tiles())
        wall = set(self.tp.wall.wall)
        for lot in self.tp.lots:
            for t in lot.tiles():
                self.assertNotIn(t, roads, "a building never sits on a street")
                self.assertNotIn(t, wall, "a building never sits on the wall")

    def test_all_buildings_inside_the_disc(self):
        cx, cy, r = self.tp.cx, self.tp.cy, self.tp.radius
        for lot in self.tp.lots:
            for (x, y) in lot.tiles():
                self.assertLessEqual((x - cx) ** 2 + (y - cy) ** 2, r * r + 1)

    def test_core_lots_are_walled(self):
        core = self.tp.core_lots()
        self.assertTrue(core, "the defended core holds buildings")
        for lot in core:
            self.assertTrue(self.tp.wall.encloses(*lot.center()))
        # the cathedral / hall belong to the core
        core_kinds = {lot.kind for lot in core}
        self.assertTrue({"cathedral", "temple", "hall"} & core_kinds,
                        "the sacred/civic landmarks are inside the walls")

    def test_deterministic(self):
        a = plan_town(80, 68, 40, size="town", seed=5)
        b = plan_town(80, 68, 40, size="town", seed=5)
        self.assertEqual(a.building_count(), b.building_count())
        self.assertEqual([(l.x, l.y, l.kind) for l in a.lots],
                         [(l.x, l.y, l.kind) for l in b.lots])


if __name__ == "__main__":
    unittest.main()
