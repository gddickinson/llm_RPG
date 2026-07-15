"""P36.1 — realistic heightmap terrain + biomes + the realistic worldgen mode."""

import os as _os
import tempfile as _tempfile
_os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_rg_"))

import unittest
from collections import Counter

import numpy as np

from world import realistic_gen as rg
from world.world_map import TerrainType as T


class TestHeightmap(unittest.TestCase):
    def test_fbm_normalised_and_shaped(self):
        f = rg.fbm(40, 30, seed=5)
        self.assertEqual(f.shape, (30, 40))
        self.assertGreaterEqual(float(f.min()), 0.0)
        self.assertLessEqual(float(f.max()), 1.0 + 1e-6)

    def test_seed_reproducible(self):
        a = rg.fbm(32, 32, seed=9)
        b = rg.fbm(32, 32, seed=9)
        c = rg.fbm(32, 32, seed=10)
        self.assertTrue(np.allclose(a, b))
        self.assertFalse(np.allclose(a, c))

    def test_terrain_for_bands(self):
        self.assertEqual(rg.terrain_for(0.10, 0.5), T.WATER)     # basin → sea
        self.assertEqual(rg.terrain_for(0.90, 0.5), T.MOUNTAIN)  # peak
        self.assertEqual(rg.terrain_for(0.50, 0.9), T.FOREST)    # wet mid → forest
        self.assertEqual(rg.terrain_for(0.35, 0.9), T.SWAMP)     # wet lowland → marsh
        self.assertEqual(rg.terrain_for(0.50, 0.2), T.GRASS)     # dry mid → plain


class TestAssign(unittest.TestCase):
    def _grid(self, w, h):
        import world.world_map as wm
        m = wm.WorldMap(w, h)
        return m

    def test_produces_a_varied_landscape(self):
        m = self._grid(80, 50)
        rg.assign_terrain(m, seed=3)
        c = Counter(m.terrain[y][x] for y in range(50) for x in range(80))
        for t in (T.WATER, T.GRASS, T.FOREST, T.MOUNTAIN):
            self.assertGreater(c[t], 0, f"expected some {t.value}")
        # water present but not the whole map
        self.assertLess(c[T.WATER], 50 * 80 * 0.7)


class TestRivers(unittest.TestCase):
    def test_flow_accumulates_downhill(self):
        # a slope decreasing left→right: drainage piles up at the low end
        elev = np.tile(np.linspace(1.0, 0.0, 12), (6, 1)).astype(np.float32)
        acc = rg.flow_accumulation(elev)
        self.assertGreater(float(acc[:, -1].sum()), float(acc[:, 0].sum()))

    def test_carve_rivers_threads_water_on_land(self):
        import world.world_map as wm
        m = wm.WorldMap(80, 50)
        elev = rg.assign_terrain(m, 7)
        n = rg.carve_rivers(m, elev)
        self.assertGreater(n, 0)
        self.assertLess(n, 80 * 50 * 0.10)          # thin rivers, not a flood


class TestRealisticMode(unittest.TestCase):
    def test_generates_playable_world(self):
        from world.world import World
        import world.world_map as wm
        from world.world_generator import WorldGenerator
        w = World()
        w.map = wm.WorldMap(100, 60)
        WorldGenerator(w, seed=7, mode="realistic").generate()
        self.assertGreater(len(w.locations), 3)
        oak = next((l for l in w.locations if "Oakvale" in l.name), None)
        self.assertIsNotNone(oak)
        # the town clearing is walkable — no deep water inside its footprint
        for y in range(oak.y, oak.y + oak.height):
            for x in range(oak.x, oak.x + oak.width):
                self.assertNotEqual(w.map.terrain[y][x], T.WATER)


class TestPlayable(unittest.TestCase):
    def test_hero_can_walk_out_of_the_walled_start_town(self):
        """Regression (George): a realistic world walled Oakvale with heightmap
        water/mountains inside, trapping the hero. The fortified courtyard must be
        walkable and a gate reachable — the hero can roam far out."""
        from engine.game_engine import GameEngine
        from collections import deque
        e = GameEngine(llm_provider="heuristic", enable_npc_processes=False,
                       world_kind="realistic")
        e.start_game()
        try:
            wmap = e.world.map
            px, py = e.player.position
            oak = next((l for l in e.world.locations
                        if l.name == "Oakvale Village"), None)
            easy = (T.GRASS, T.ROAD, T.BRIDGE, T.FOREST, T.RUBBLE, T.FARMLAND)
            seen, q = {(px, py)}, deque([(px, py)])
            while q:
                x, y = q.popleft()
                for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nx, ny = x + a, y + b
                    if 0 <= nx < wmap.width and 0 <= ny < wmap.height \
                            and (nx, ny) not in seen \
                            and wmap.terrain[ny][nx] in easy:
                        seen.add((nx, ny))
                        q.append((nx, ny))
            far = max((abs(x - oak.x) + abs(y - oak.y) for x, y in seen),
                      default=0) if oak else 999
            self.assertGreater(len(seen), 300)      # not boxed in
            self.assertGreater(far, 25)             # roams well beyond the walls
        finally:
            e.end_game()

    def test_chronicle_seeded_from_history(self):
        from engine.game_engine import GameEngine
        e = GameEngine(llm_provider="heuristic", enable_npc_processes=False,
                       world_kind="realistic")
        e.start_game()
        try:
            self.assertTrue(getattr(e.chronicle, "pregame", []),
                            "the age's chronicle should show in the Y-journal")
        finally:
            e.end_game()


if __name__ == "__main__":
    unittest.main()
