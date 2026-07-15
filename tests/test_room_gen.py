"""P36.4 — BSP room subdivision + subdivided building interiors."""

import os as _os
import tempfile as _tempfile
_os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_rgn_"))

import unittest
from collections import deque

from world import room_gen as rg
from world.world_map import TerrainType as T


class TestSubdivide(unittest.TestCase):
    def test_grid_shape_and_border(self):
        grid, rooms = rg.subdivide(16, 11, seed=1)
        self.assertEqual(len(grid), 11)
        self.assertEqual(len(grid[0]), 16)
        self.assertTrue(all(grid[0][x] == rg.WALL for x in range(16)))
        self.assertTrue(all(grid[y][0] == rg.WALL for y in range(11)))

    def test_multiple_rooms_and_doors(self):
        grid, rooms = rg.subdivide(20, 12, seed=4)
        self.assertGreaterEqual(len(rooms), 3)          # a real floorplan
        doors = sum(1 for row in grid for c in row if c == rg.DOOR)
        self.assertGreater(doors, 0)

    def test_always_connected(self):
        for s in range(40):
            grid, _ = rg.subdivide(17, 12, seed=s)
            self.assertTrue(rg.is_connected(grid), f"seed {s} not connected")

    def test_seed_reproducible(self):
        a, _ = rg.subdivide(16, 11, seed=7)
        b, _ = rg.subdivide(16, 11, seed=7)
        c, _ = rg.subdivide(16, 11, seed=8)
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)


class TestSubdividedInterior(unittest.TestCase):
    def _reachable(self, inter):
        dx, dy = inter.door
        start = (dx, dy - 1)
        seen, q = {start}, deque([start])
        while q:
            x, y = q.popleft()
            for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = x + a, y + b
                if 0 <= nx < inter.width and 0 <= ny < inter.height \
                        and (nx, ny) not in seen \
                        and inter.terrain[ny][nx] != T.BUILDING:
                    seen.add((nx, ny))
                    q.append((nx, ny))
        floor = sum(1 for row in inter.terrain for c in row if c != T.BUILDING)
        return len(seen), floor

    def _fit(self, fw, fh):
        from world.interiors import make_default_interior, fit_to_footprint
        from world.location import Location
        inter = make_default_interior("Hall")
        fit_to_footprint(inter, Location("Hall", "", 0, 0, fw, fh))
        return inter

    def test_big_building_is_multi_room_and_connected(self):
        inter = self._fit(4, 4)
        inner = sum(1 for y in range(1, inter.height - 1)
                    for x in range(1, inter.width - 1)
                    if inter.terrain[y][x] == T.BUILDING)
        self.assertGreater(inner, 0, "expected interior partition walls")
        reached, floor = self._reachable(inter)
        self.assertEqual(reached, floor, "the entrance must reach every room")

    def test_small_hut_stays_one_room(self):
        inter = self._fit(2, 2)                          # tiny footprint
        inner = sum(1 for y in range(1, inter.height - 1)
                    for x in range(1, inter.width - 1)
                    if inter.terrain[y][x] == T.BUILDING)
        self.assertEqual(inner, 0, "a hut keeps its single open room")


if __name__ == "__main__":
    unittest.main()
