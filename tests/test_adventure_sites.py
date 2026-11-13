"""Adventure areas are spread across the map (world/adventure_sites.pick_site),
not stacked first-from-top-left, and wetland adventures get wetland."""

import os
import random
import unittest

from world.adventure_sites import ADV_SPACING, paint_marsh, pick_site
from world.world_map import TerrainType


def _areas(engine):
    out = {}
    for loc in engine.world.locations:
        adv = (loc.properties or {}).get("adventure")
        if adv:
            out.setdefault(adv, []).append((loc.x, loc.y))
    return out


class TestAdventureSitesCombined(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._flag = os.environ.pop("LLM_RPG_NO_ADVENTURERS", None)
        from engine.game_engine import GameEngine
        cls.engine = GameEngine(llm_provider="heuristic", enable_npc_processes=False,
                                world_kind="combined", seed=21)
        cls.engine.start_game()
        cls.areas = _areas(cls.engine)

    @classmethod
    def tearDownClass(cls):
        os.environ["LLM_RPG_NO_ADVENTURERS"] = cls._flag or "1"
        try:
            cls.engine.end_game()
        except Exception:
            pass

    def test_all_five_adventures_seeded(self):
        self.assertEqual(len(self.areas), 5, self.areas)

    def test_not_stacked_on_the_top_edge(self):
        edge = [p for pts in self.areas.values() for p in pts if p[1] <= 1]
        self.assertLessEqual(len(edge), 1, edge)

    def test_different_adventures_keep_their_distance(self):
        items = [(a, p) for a, pts in self.areas.items() for p in pts]
        for i, (a, p) in enumerate(items):
            for b, q in items[i + 1:]:
                if a != b:
                    self.assertGreaterEqual(abs(p[0] - q[0]) + abs(p[1] - q[1]), ADV_SPACING,
                                            f"{a}{p} vs {b}{q}")

    def test_swamp_adventure_sits_by_wetland(self):
        wmap = self.engine.world.map
        wet = (TerrainType.SWAMP, TerrainType.WATER)
        for x, y in self.areas["sunken_tome"]:
            near = [wmap.terrain[y + dy][x + dx] for dx in (-1, 0, 1) for dy in (-1, 0, 1)]
            self.assertTrue(any(t in wet for t in near), (x, y))


class TestPickSiteUnit(unittest.TestCase):
    def setUp(self):
        from engine.game_engine import GameEngine
        self.engine = GameEngine(llm_provider="heuristic", enable_npc_processes=False, seed=3)
        self.engine.start_game()
        self.wmap = self.engine.world.map

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_seeded_choice_is_reproducible(self):
        a = pick_site(self.engine, "forest", [], 10, random.Random(5))
        b = pick_site(self.engine, "forest", [], 10, random.Random(5))
        self.assertEqual(a, b)

    def test_no_wetland_makes_a_marsh(self):
        w = self.wmap
        for y in range(w.height):              # drain every swamp and water tile
            for x in range(w.width):
                if w.terrain[y][x] in (TerrainType.SWAMP, TerrainType.WATER):
                    w.terrain[y][x] = TerrainType.GRASS
        x, y = pick_site(self.engine, "swamp", [], 10, random.Random(1))
        self.assertEqual(w.terrain[y][x], TerrainType.SWAMP)

    def test_paint_marsh_spares_named_places(self):
        w = self.wmap
        w.terrain[5][5] = TerrainType.GRASS
        w.terrain[5][6] = TerrainType.GRASS
        n = paint_marsh(w, (5, 5), taken={(6, 5)}, radius=1)
        self.assertGreater(n, 0)
        self.assertEqual(w.terrain[5][6], TerrainType.GRASS)


if __name__ == "__main__":
    unittest.main()
