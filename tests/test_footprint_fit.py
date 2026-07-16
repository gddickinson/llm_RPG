"""Footprint-matched interior tests (P9A.7b)."""

import unittest

from engine.game_engine import GameEngine
from world.world_map import TerrainType


class TestFootprintFit(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _pairs(self):
        for loc in self.engine.world.locations:
            inter = self.engine.interiors.get(loc.name)
            if inter is None:
                continue
            # Authored structures (P9.1) keep their designed grids
            if getattr(inter, "structure_id", None):
                continue
            yield loc, inter

    def test_interior_size_scales_with_footprint(self):
        # GX.3 SCALE-UP: ×4 multiplier + bigger caps (a 2×2 → 10×10, not 8×8)
        for loc, inter in self._pairs():
            self.assertEqual(inter.width,
                             max(7, min(28, loc.width * 4 + 2)),
                             loc.name)
            self.assertEqual(inter.height,
                             max(6, min(22, loc.height * 4 + 2)),
                             loc.name)

    def test_wide_buildings_open_into_wide_rooms(self):
        wide = [(l, i) for l, i in self._pairs()
                if l.width > l.height]
        for loc, inter in wide:
            self.assertGreater(inter.width, inter.height, loc.name)

    def test_door_is_south_center_everywhere(self):
        for loc, inter in self._pairs():
            self.assertEqual(inter.door,
                             (inter.width // 2, inter.height - 1),
                             loc.name)
            dx, dy = inter.door
            self.assertEqual(inter.terrain[dy][dx], TerrainType.ROAD,
                             loc.name)

    def test_furniture_stays_inside_the_walls(self):
        for loc, inter in self._pairs():
            for piece in inter.furniture:
                self.assertTrue(
                    1 <= piece["x"] <= inter.width - 2,
                    f"{loc.name}: {piece['name']} x out of bounds")
                self.assertTrue(
                    1 <= piece["y"] <= inter.height - 2,
                    f"{loc.name}: {piece['name']} y out of bounds")

    def test_no_two_pieces_share_a_tile(self):
        for loc, inter in self._pairs():
            spots = [(p["x"], p["y"]) for p in inter.furniture]
            self.assertEqual(len(spots), len(set(spots)), loc.name)

    def test_furniture_kinds_survive_the_fit(self):
        tavern = next(i for n, i in self.engine.interiors.items()
                      if "tavern" in n.lower())
        names = [f["name"] for f in tavern.furniture]
        self.assertIn("Hearth", names)

    def test_lofts_match_their_ground_floor(self):
        tavern = next(i for n, i in self.engine.interiors.items()
                      if "tavern" in n.lower())
        loft = tavern.level_above
        self.assertIsNotNone(loft)
        self.assertEqual((loft.width, loft.height),
                         (tavern.width, tavern.height))

    def test_a_hut_is_smaller_inside_than_a_hall(self):
        small = [i for l, i in self._pairs()
                 if l.width * l.height <= 4]
        large = [i for l, i in self._pairs()
                 if l.width * l.height >= 9]
        if not small or not large:
            self.skipTest("world lacks size contrast")
        self.assertLess(max(i.width * i.height for i in small),
                        max(i.width * i.height for i in large))


if __name__ == "__main__":
    unittest.main()
