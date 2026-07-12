"""The Bloodstone realm layout (P18.4): the castle, the gate town, and the
ring of farming villages that supply it — planted on the world map."""

import os as _os
import tempfile as _tempfile
_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_lib_"))

import unittest

from world.world import World
from world.world_map import WorldMap, TerrainType
from world.castle_region import (build_castle_region, CASTLE_NAME,
                                 TOWN_NAME, VILLAGES)


class TestLayout(unittest.TestCase):
    def setUp(self):
        self.world = World()
        self.world.map = WorldMap(120, 80)
        self.plan = build_castle_region(self.world)

    def _names(self):
        return {l.name for l in self.world.locations}

    def test_the_whole_realm_is_planted(self):
        names = self._names()
        self.assertIn(CASTLE_NAME, names)
        self.assertIn(TOWN_NAME, names)
        for v in VILLAGES:
            self.assertIn(v, names)

    def test_the_castle_is_a_walled_fortress_with_a_gate(self):
        castle = next(l for l in self.world.locations
                      if l.name == CASTLE_NAME)
        self.assertEqual((castle.properties or {}).get("type"), "castle")
        wm = self.world.map
        # a curtain wall of BUILDING around a grass bailey, breached by one
        # ROAD gate in the south wall
        edge_building = 0
        for xx in range(castle.x, castle.x + castle.width):
            if wm.terrain[castle.y][xx] == TerrainType.BUILDING:
                edge_building += 1
        self.assertGreater(edge_building, castle.width // 2,
                           "the north wall is stone")
        gate = sum(1 for xx in range(castle.x, castle.x + castle.width)
                   if wm.terrain[castle.y + castle.height - 1][xx]
                   == TerrainType.ROAD)
        self.assertEqual(gate, 1, "one gate through the south wall")

    def test_villages_have_farmland(self):
        farm = sum(row.count(TerrainType.FARMLAND)
                   for row in self.world.map.terrain)
        self.assertGreater(farm, 10, "the villages work real fields")

    def test_roads_stitch_the_supply_routes(self):
        road = sum(row.count(TerrainType.ROAD)
                   for row in self.world.map.terrain)
        self.assertGreater(road, 20, "gate, town and villages are linked")

    def test_the_town_has_its_trades(self):
        types = {(l.properties or {}).get("type")
                 for l in self.world.locations}
        for t in ("tavern", "shop", "temple", "forge"):
            self.assertIn(t, types, f"the town needs a {t}")


class TestIntegration(unittest.TestCase):
    def setUp(self):
        from engine.game_engine import GameEngine
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False)
        self.engine.start_game()
        build_castle_region(self.engine.world)

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_the_castle_structure_attaches_to_its_footprint(self):
        from world.structures import StructureBuilder
        StructureBuilder(self.engine).build()
        hall = self.engine.interiors.get(CASTLE_NAME)
        self.assertIsNotNone(hall, "the 7-floor keep attaches to the gate")
        self.assertEqual(hall.structure_id, "bloodstone_castle")
        # you can descend the full keep
        depth, z = 1, hall
        while getattr(z, "level_below", None) is not None:
            z, depth = z.level_below, depth + 1
        self.assertEqual(depth, 5, "hall down to the crypt")

    def test_town_and_villages_are_production_settlements(self):
        from engine.production_loop import ProductionSystem
        prod = ProductionSystem(self.engine)
        names = {s.name for s in prod._settlements()}
        self.assertIn(TOWN_NAME, names, "the town produces & trades")
        for v in VILLAGES:
            self.assertIn(v, names, f"{v} is a supply settlement")


if __name__ == "__main__":
    unittest.main()
