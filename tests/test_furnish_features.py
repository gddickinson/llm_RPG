"""BLD.3 — feature-composition furnishing: named arrangements (an L-shaped bar
counter, pew rows with an aisle, a colonnade, a carpet runner, an altar on the
far wall) instead of scattered props; plus the door-apron exclusion that keeps
doorways clear."""

import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import random
import unittest

from world import furnish_features as FF
from world.interiors import Interior
from world.world_map import TerrainType as T


def _room(w=12, h=9):
    inter = Interior(name="room", width=w, height=h)
    inter.init_grid()
    inter.door = (w // 2, h - 1)
    return inter


class TestCompositions(unittest.TestCase):
    def setUp(self):
        self.rng = random.Random(3)

    def test_bar_counter_forms_an_L(self):
        inter = _room()
        rect = (1, 1, 10, 6)
        placed = FF.bar_counter(inter, rect, set(), self.rng)
        xs = {p[0] for p in placed}
        ys = {p[1] for p in placed}
        # a horizontal arm (several x at one y) AND a vertical arm (several y at
        # one x) — an L, not a single line
        horiz = max(sum(1 for p in placed if p[1] == y) for y in ys)
        vert = max(sum(1 for p in placed if p[0] == x) for x in xs)
        self.assertGreaterEqual(horiz, 2)
        self.assertGreaterEqual(vert, 2)
        self.assertTrue(all(n == "Table" for _, _, n in placed))

    def test_pew_rows_are_parallel_with_an_aisle(self):
        inter = _room()
        rect = (1, 1, 10, 6)
        placed = FF.pew_rows(inter, rect, set(), self.rng)
        rows = {p[1] for p in placed}
        self.assertGreaterEqual(len(rows), 2, "multiple parallel rows")
        aisle = 1 + 10 // 2
        self.assertFalse(any(p[0] == aisle for p in placed), "aisle stays clear")

    def test_pillar_row_is_two_columns(self):
        inter = _room()
        placed = FF.pillar_row(inter, (1, 1, 10, 6), set(), self.rng)
        cols = {p[0] for p in placed}
        self.assertGreaterEqual(len(cols), 2)
        self.assertTrue(all(n == "Pillar" for _, _, n in placed))

    def test_carpet_runner_down_the_centre(self):
        inter = _room()
        placed = FF.carpet_runner(inter, (1, 1, 10, 6), set(), self.rng)
        self.assertTrue(placed)
        self.assertEqual({p[0] for p in placed}, {1 + 10 // 2})

    def test_altar_on_the_far_wall(self):
        inter = _room()
        placed = FF.altar_end(inter, (1, 1, 10, 6), set(), self.rng)
        self.assertEqual(len(placed), 1)
        x, y, name = placed[0]
        self.assertEqual(name, "Altar")
        self.assertEqual(y, 1, "altar sits at the far (top) wall")


class TestDoorApron(unittest.TestCase):
    def test_apron_covers_a_doorway_gap(self):
        # a room split by a vertical wall with one doorway gap
        inter = _room(11, 7)
        for y in range(1, 6):
            inter.terrain[y][5] = T.BUILDING     # internal wall
        inter.terrain[3][5] = T.GRASS            # a doorway through it
        ap = FF.apron(inter)
        self.assertIn((5, 3), ap, "the doorway tile is in the apron")
        self.assertIn((4, 3), ap, "the tile in front of it too")
        self.assertIn((6, 3), ap)

    def test_furnish_typed_never_blocks_a_doorway(self):
        from world import room_gen, room_plan
        inter = _room(13, 9)
        grid, rooms = room_gen.subdivide(13, 9, 5, min_room=2, max_depth=2)
        grid[7][6] = room_gen.FLOOR
        for y in range(8):
            for x in range(1, 12):
                if grid[y][x] == room_gen.WALL:
                    inter.terrain[y][x] = T.BUILDING
        room_plan.furnish_typed(inter, rooms, "tavern", seed=5)
        ap = FF.apron(inter)
        on = [(f["x"], f["y"]) for f in inter.furniture
              if (f["x"], f["y"]) in ap]
        self.assertFalse(on, f"furniture blocks a doorway: {on}")


if __name__ == "__main__":
    unittest.main()
