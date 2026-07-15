"""Worldgen leap (P16.6): elevation, downhill rivers, site scoring."""

import os as _os
import tempfile as _tempfile
import unittest

_os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
_os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_lib_"))

from world.river_gen import (elevation_field, trace_river, is_shore,
                             score_site)                  # noqa: E402
from world.world_map import TerrainType                   # noqa: E402


class TestElevation(unittest.TestCase):
    def test_shape_and_determinism(self):
        a = elevation_field(40, 24, seed=7)
        b = elevation_field(40, 24, seed=7)
        self.assertEqual(len(a), 24)
        self.assertEqual(len(a[0]), 40)
        self.assertEqual(a, b)                       # seed-reproducible

    def test_different_seeds_differ(self):
        self.assertNotEqual(elevation_field(40, 24, seed=1),
                            elevation_field(40, 24, seed=2))

    def test_valley_is_the_low_ground(self):
        # in every column the minimum-elevation row is the valley floor;
        # elevation rises away from it
        elev = elevation_field(40, 24, seed=3)
        for x in range(0, 40, 8):
            col = [elev[y][x] for y in range(24)]
            vy = col.index(min(col))
            self.assertLess(col[vy], col[0])          # lower than the top
            self.assertLess(col[vy], col[-1])         # lower than the bottom


class TestRiver(unittest.TestCase):
    def test_one_tile_per_column_and_connected(self):
        elev = elevation_field(40, 24, seed=5)
        path = trace_river(elev, 40, 24)
        self.assertEqual(len(path), 40)
        xs = [x for x, _ in path]
        self.assertEqual(xs, list(range(40)))        # one per column
        for (x0, y0), (x1, y1) in zip(path, path[1:]):
            self.assertLessEqual(abs(y1 - y0), 1)     # continuous course

    def test_stays_off_the_edges(self):
        elev = elevation_field(40, 24, seed=5)
        for _, y in trace_river(elev, 40, 24):
            self.assertTrue(2 <= y <= 24 - 3)

    def test_follows_the_valley(self):
        # the river should sit near the low valley floor, not wander to
        # the high ground
        elev = elevation_field(60, 30, seed=9)
        path = trace_river(elev, 60, 30)
        for x, y in path:
            col = [elev[yy][x] for yy in range(2, 30 - 3)]
            self.assertLessEqual(elev[y][x], min(col) + 2.0)

    def test_deterministic(self):
        e1 = elevation_field(50, 30, seed=11)
        e2 = elevation_field(50, 30, seed=11)
        self.assertEqual(trace_river(e1, 50, 30), trace_river(e2, 50, 30))


class TestShoreAndSites(unittest.TestCase):
    def _grid(self):
        g = [[TerrainType.GRASS for _ in range(10)] for _ in range(10)]
        g[5][5] = TerrainType.WATER
        return g

    def test_is_shore(self):
        g = self._grid()
        self.assertTrue(is_shore(g, 5, 4))           # north of the water
        self.assertTrue(is_shore(g, 4, 5))           # west of the water
        self.assertFalse(is_shore(g, 5, 5))          # the water itself
        self.assertFalse(is_shore(g, 0, 0))          # dry inland

    def test_score_prefers_water_variety_and_off_edge(self):
        g = self._grid()
        g[5][6] = TerrainType.FOREST
        g[6][5] = TerrainType.MOUNTAIN
        near = score_site(g, 5, 4, radius=3)          # by the water + varied
        corner = score_site(g, 0, 0, radius=3)        # dry, on the edge
        self.assertGreater(near, corner)

    def test_edge_sites_are_penalised(self):
        g = self._grid()
        self.assertLess(score_site(g, 1, 1, radius=3),
                        score_site(g, 5, 4, radius=3))


class TestWiredIntoWorldgen(unittest.TestCase):
    def test_a_generated_world_has_an_elevation_river(self):
        from engine.game_engine import GameEngine
        e = GameEngine(llm_provider="heuristic", enable_npc_processes=False)
        e.start_game()
        wmap = e.world.map
        water = sum(1 for y in range(wmap.height) for x in range(wmap.width)
                    if wmap.terrain[y][x] == TerrainType.WATER)
        self.assertGreater(water, wmap.width // 3, "a river crosses the map")
        e.end_game()


if __name__ == "__main__":
    unittest.main()
