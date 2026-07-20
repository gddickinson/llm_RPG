"""OAKVALE T5 — stamping a TownPlan onto the world (headless)."""

import unittest

from world.world import World
from world.world_map import TerrainType
from world.town.town_gen import plan_town
from world.town.stamp import stamp_town, clear_disc


class TestStamp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.world = World(110, 110)
        for y in range(110):
            for x in range(110):
                cls.world.map.terrain[y][x] = TerrainType.GRASS
        cls.plan = plan_town(55, 55, 34, size="town", seed=20)
        cls.res = stamp_town(cls.world, cls.plan, name="Oakvale")

    def test_reports_the_build(self):
        self.assertEqual(self.res["buildings"], len(self.plan.lots))
        self.assertGreater(self.res["buildings"], 80)
        self.assertGreaterEqual(self.res["gates"], 3)

    def test_named_landmark_locations_carry_their_kind(self):
        cath = [l for l in self.world.locations if "Cathedral" in l.name]
        self.assertTrue(cath, "the cathedral is a Location")
        self.assertEqual(cath[0].get_property("kind"), "cathedral")
        self.assertEqual(cath[0].get_property("type"), "cathedral")

    def test_building_tiles_are_building_terrain(self):
        wm = self.world.map
        for lot in self.plan.lots[:30]:
            for (x, y) in lot.tiles():
                self.assertEqual(wm.terrain[y][x], TerrainType.BUILDING)

    def test_gates_are_passable_road(self):
        wm = self.world.map
        for (gx, gy) in self.plan.wall.gates:
            self.assertEqual(wm.terrain[gy][gx], TerrainType.ROAD,
                             "a gate is passable")

    def test_building_names_are_unique(self):
        names = [l.name for l in self.world.locations
                 if l.get_property("kind")]
        self.assertEqual(len(names), len(set(names)),
                         "unique names — interiors key on Location.name")

    def test_town_marker_records_gates_and_towers(self):
        town = next(l for l in self.world.locations
                    if l.name == "Oakvale" and l.get_property("town"))
        self.assertEqual(len(town.get_property("gates")),
                         len(self.plan.wall.gates))
        self.assertTrue(town.get_property("towers"))

    def test_a_forge_is_tagged_for_the_smith(self):
        forges = [l for l in self.world.locations
                  if l.get_property("kind") in ("forge", "smithy", "armoury")]
        self.assertTrue(forges)
        self.assertTrue(all(f.get_property("forge") for f in forges))

    def test_clear_disc_keeps_water(self):
        w = World(40, 40)
        for y in range(40):
            for x in range(40):
                w.map.terrain[y][x] = TerrainType.FOREST
        w.map.terrain[20][20] = TerrainType.WATER
        clear_disc(w.map, 20, 20, 10)
        self.assertEqual(w.map.terrain[20][20], TerrainType.WATER, "river kept")
        self.assertEqual(w.map.terrain[15][20], TerrainType.GRASS, "forest cleared")


if __name__ == "__main__":
    unittest.main()
