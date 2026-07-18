"""M0 — the Worldcraft mutation layer (the keystone).

One validated facade over WorldMap.set_terrain: what terrain can become what, by
what means (labor|magic), at what cost, gated on whom. Spells, workers, the build
tool and the DM all obey this one ruleset. Persistence is free (terrain snapshot).
"""

import unittest

from engine.game_engine import GameEngine
from engine import worldcraft as wc
from world.world_map import TerrainType
from items.item_registry import create_item


class _Base(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False)
        self.engine.start_game()
        self.wmap = self.engine.world.map
        self.p = self.engine.player

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _grass(self):
        for y in range(self.wmap.height):
            for x in range(self.wmap.width):
                if self.wmap.get_terrain_at(x, y) == TerrainType.GRASS \
                        and not wc.protected(self.engine, x, y) \
                        and (x, y) not in self.wmap.characters:
                    return x, y
        self.skipTest("no free grass tile")


class TestRules(unittest.TestCase):
    def test_rules_load(self):
        self.assertGreater(len(wc.rules()), 5)

    def test_rule_for(self):
        found = wc.rule_for(TerrainType.FOREST, TerrainType.GRASS)
        self.assertIsNotNone(found)
        self.assertEqual(found[1]["from"], "forest")

    def test_allowed_targets_differ_by_means(self):
        magic = set(wc.allowed_targets(TerrainType.GRASS, "magic"))
        labor = set(wc.allowed_targets(TerrainType.GRASS, "labor"))
        self.assertIn("water", magic)          # only magic floods
        self.assertNotIn("water", labor)
        self.assertIn("building", labor)        # labor raises a wall


class TestMutate(_Base):
    def test_magic_needs_no_actor(self):
        x, y = self._grass()
        ok, _ = wc.mutate(self.engine, x, y, "scorched", "magic")
        self.assertTrue(ok)
        self.assertEqual(self.wmap.get_terrain_at(x, y), TerrainType.SCORCHED)

    def test_invalid_transition_refused(self):
        x, y = self._grass()
        ok, why = wc.can_mutate(self.engine, x, y, "cave", "magic")
        self.assertFalse(ok)
        self.assertIn("can't turn", why)

    def test_wrong_means_refused(self):
        x, y = self._grass()
        # water is magic-only; labor can't flood
        ok, why = wc.can_mutate(self.engine, x, y, "water", "labor")
        self.assertFalse(ok)
        self.assertIn("no labor", why)

    def test_labor_consumes_resources(self):
        x, y = self._grass()
        ok, why = wc.can_mutate(self.engine, x, y, "building", "labor",
                                actor=self.p)
        self.assertFalse(ok, "no stone yet")
        self.p.add_item(create_item("stone", quantity=3))
        ok, _ = wc.mutate(self.engine, x, y, "building", "labor", actor=self.p)
        self.assertTrue(ok)
        self.assertEqual(self.wmap.get_terrain_at(x, y), TerrainType.BUILDING)
        self.assertEqual(wc._count(self.p, "stone"), 1)   # 2 consumed

    def test_labor_yields_byproduct(self):
        # clear a forest tile with an axe → grass + logs
        spot = None
        for y in range(self.wmap.height):
            for x in range(self.wmap.width):
                if self.wmap.get_terrain_at(x, y) == TerrainType.FOREST \
                        and not wc.protected(self.engine, x, y):
                    spot = (x, y)
                    break
            if spot:
                break
        if spot is None:
            self.skipTest("no forest")
        self.p.add_item(create_item("crude_axe"))    # has_tool('axe') matches
        before = wc._count(self.p, "logs")
        ok, _ = wc.mutate(self.engine, spot[0], spot[1], "grass", "labor",
                          actor=self.p)
        self.assertTrue(ok)
        self.assertEqual(self.wmap.get_terrain_at(*spot), TerrainType.GRASS)
        self.assertEqual(wc._count(self.p, "logs"), before + 2)

    def test_tool_gate(self):
        # level_mountain needs a pickaxe
        spot = None
        for y in range(self.wmap.height):
            for x in range(self.wmap.width):
                if self.wmap.get_terrain_at(x, y) == TerrainType.MOUNTAIN \
                        and not wc.protected(self.engine, x, y):
                    spot = (x, y)
                    break
            if spot:
                break
        if spot is None:
            self.skipTest("no mountain")
        ok, why = wc.can_mutate(self.engine, spot[0], spot[1], "grass",
                                "labor", actor=self.p)
        self.assertFalse(ok)
        self.assertIn("pickaxe", why)
        # but magic (earth) can do it with no tool
        ok, _ = wc.can_mutate(self.engine, spot[0], spot[1], "grass", "magic")
        self.assertTrue(ok)


class TestProtection(_Base):
    def test_typed_poi_is_protected(self):
        poi = next((l for l in self.engine.world.locations
                    if (l.properties or {}).get("type")), None)
        if poi is None:
            self.skipTest("no typed POI")
        self.assertTrue(wc.protected(self.engine, poi.x, poi.y))


class TestPersistence(_Base):
    def test_mutation_survives_save_load(self):
        import tempfile
        import os
        x, y = self._grass()
        wc.mutate(self.engine, x, y, "scorched", "magic")
        path = os.path.join(tempfile.mkdtemp(), "wc.json")
        self.engine.save_game(path)
        eng2 = GameEngine(llm_provider="heuristic", enable_npc_processes=False)
        eng2.load_game(path)
        self.assertEqual(eng2.world.map.get_terrain_at(x, y),
                         TerrainType.SCORCHED)
        try:
            eng2.end_game()
        except Exception:
            pass


if __name__ == "__main__":
    unittest.main()
