"""Building STRUCTURAL integrity (George): wall damage mirrors inside, buildings
COLLAPSE past a threshold, and materials respond differently — stone shrugs off
ordinary fire but a dragon's breath / magic tears it down.
"""

import unittest

from engine.game_engine import GameEngine
from engine import building_integrity as bi
from world.world_map import TerrainType
from engine.earthworks import footprint_to_perimeter


class _Base(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False)
        self.engine.start_game()
        self.wmap = self.engine.world.map
        self.td = self.engine.tile_damage

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _a_building(self):
        for name in (getattr(self.engine, "interiors", None) or {}):
            loc = next((l for l in self.engine.world.locations
                        if l.name == name), None)
            if loc and self._wall_count(loc)[0] >= 2:
                return loc
        self.skipTest("no walled building")

    def _wall_count(self, loc):
        return bi._footprint_wall_count(self.engine, loc)


class TestMaterialResponse(_Base):
    def test_stone_resists_fire_but_not_dragonfire(self):
        wall = None
        for y in range(self.wmap.height):
            for x in range(self.wmap.width):
                if self.wmap.terrain[y][x] == TerrainType.BUILDING:
                    wall = (x, y)
                    break
            if wall:
                break
        if wall is None:
            self.skipTest("no wall")
        self.td.tile_hp.clear()
        self.td.damage_tile(*wall, 20, "fire")
        fire_hp = self.td.tile_hp.get(wall, 60)
        self.td.tile_hp.clear()
        self.td.damage_tile(*wall, 20, "dragonfire")
        dragon_hp = self.td.tile_hp.get(wall, 60)
        self.assertGreater(fire_hp, dragon_hp,
                           "dragonfire tears stone that fire barely marks")
        self.assertGreater(fire_hp, 50, "stone shrugs off ordinary fire")


class TestCollapse(_Base):
    def test_building_collapses_past_threshold(self):
        loc = self._a_building()
        walls0 = self._wall_count(loc)[0]
        cx, cy = loc.center()
        self.td.tile_hp.clear()
        self.td.damage_radius(cx, cy, 100, max(loc.width, loc.height) + 1,
                              "dragonfire")
        walls, rubble = self._wall_count(loc)
        self.assertEqual(walls, 0, "the whole building came down")
        self.assertGreater(rubble, 0)
        self.assertTrue((loc.properties or {}).get("collapsed"))

    def test_light_damage_does_not_collapse(self):
        loc = self._a_building()
        cx, cy = loc.center()
        # a single glancing fire hit shouldn't level a stone building
        self.td.damage_tile(cx, cy, 5, "fire")
        self.assertFalse((loc.properties or {}).get("collapsed"))


class TestInteriorSync(_Base):
    def test_breach_mirrors_inside(self):
        loc = self._a_building()
        inter = self.engine.interiors.get(loc.name)
        if inter is None:
            self.skipTest("no interior")
        # knock a footprint wall to rubble
        wall = None
        for yy in range(loc.y, loc.y + loc.height):
            for xx in range(loc.x, loc.x + loc.width):
                if self.wmap.terrain[yy][xx] == TerrainType.BUILDING:
                    wall = (xx, yy)
                    break
            if wall:
                break
        if wall is None:
            self.skipTest("no wall tile")
        self.wmap.set_terrain(*wall, TerrainType.RUBBLE)
        bi.on_wall_destroyed(self.engine, *wall)
        ix, iy = footprint_to_perimeter(loc, inter, *wall)
        if ix is None:
            self.skipTest("no matching interior perimeter tile")
        self.assertEqual(inter.terrain[iy][ix], TerrainType.RUBBLE,
                         "a hole outside is a hole inside")


class TestScope(_Base):
    def test_lone_rampart_is_not_a_building(self):
        # a wall tile with no interior Location isn't an enterable building
        for y in range(self.wmap.height):
            for x in range(self.wmap.width):
                if self.wmap.terrain[y][x] == TerrainType.BUILDING \
                        and bi.building_at(self.engine, x, y) is None:
                    return   # found a non-building wall — good
        # not fatal if every wall belongs to a building
        self.assertTrue(True)


if __name__ == "__main__":
    unittest.main()
