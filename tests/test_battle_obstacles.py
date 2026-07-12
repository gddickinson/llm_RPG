"""Terrain & obstacles (P17.E2): ditches slow, moats block, and a flank
anchored on impassable ground cannot be turned."""

import unittest

from engine.battle import BattleField, Squad, BattleSession
from engine.battle import battle_ai as ai
from engine.battle import battle_terrain as terrain


class _Max:
    def randint(self, a, b):
        return b


class TestObstacles(unittest.TestCase):
    def test_moats_and_cliffs_block(self):
        bf = BattleField(10, 10)
        for kind in ("moat", "cliff", "chasm"):
            bf.terrain[4][4] = kind
            self.assertFalse(bf.passable(4, 4), f"{kind} is impassable")
        bf.terrain[4][4] = "grass"
        self.assertTrue(bf.passable(4, 4))

    def test_a_soldier_cannot_wade_a_moat(self):
        bf = BattleField(10, 10)
        sq = Squad.raise_squad("s", "red", "infantry_sword", [(3, 3)])
        bf.add_squad(sq)
        bf.terrain[3][4] = "moat"
        self.assertFalse(bf.move_soldier(sq.soldiers[0], 4, 3))

    def test_move_cost(self):
        bf = BattleField(10, 10)
        bf.terrain[2][2] = "stream"
        bf.terrain[2][3] = "bog"
        self.assertEqual(terrain.move_cost(bf, 2, 2), 2)
        self.assertEqual(terrain.move_cost(bf, 3, 2), 3)
        self.assertEqual(terrain.move_cost(bf, 5, 5), 1)       # open ground
        self.assertEqual(terrain.move_cost(bf, -1, 0), 1)      # off-map


class TestWadingIsSlow(unittest.TestCase):
    def _advance(self, corridor):
        bf = BattleField(30, 12)
        mover = Squad.raise_squad("m", "red", "cavalry_light", [(2, 6)])
        mover.set_order("charge", "f")
        foe = Squad.raise_squad("f", "blue", "infantry_sword", [(25, 6)])
        for x in range(3, 25):
            bf.terrain[6][x] = corridor
        bf.add_squad(mover)
        bf.add_squad(foe)
        x0 = mover.soldiers[0].x
        BattleSession(bf, seed=1).tick()
        return mover.soldiers[0].x - x0

    def test_wading_a_stream_is_slower_than_open_ground(self):
        self.assertLess(self._advance("stream"), self._advance("grass"))


class TestAnchoredFlank(unittest.TestCase):
    def _defender(self, north_kind="grass"):
        bf = BattleField(14, 14)
        tgt = Squad.raise_squad("t", "blue", "infantry_sword", [(6, 6)])
        tgt.soldiers[0].facing = (1, 0)             # faces east
        bf.terrain[5][6] = north_kind                # the north-flank tile
        arch = Squad.raise_squad("a", "red", "archer_longbow", [(6, 3)])
        bf.add_squad(tgt)
        bf.add_squad(arch)
        return bf, arch, tgt

    def test_anchored_predicate(self):
        bf, arch, tgt = self._defender("wall")
        self.assertTrue(terrain.anchored(bf, (6, 3), (6, 6), (1, 0)))
        bf2, _, _ = self._defender("grass")
        self.assertFalse(terrain.anchored(bf2, (6, 3), (6, 6), (1, 0)))
        # a frontal blow is never "anchored"
        self.assertFalse(terrain.anchored(bf, (7, 6), (6, 6), (1, 0)))

    def test_anchored_flank_takes_no_arc_bonus(self):
        bf, arch, tgt = self._defender("wall")           # river/wall anchor
        self.assertEqual(
            ai._position_mods(bf, arch.soldiers[0], tgt.soldiers[0]),
            (0, 1.0))                                    # front, not flank
        bf2, arch2, tgt2 = self._defender("grass")       # open flank
        self.assertEqual(
            ai._position_mods(bf2, arch2.soldiers[0], tgt2.soldiers[0]),
            (2, 1.25))                                   # a real flank

    def test_anchored_flank_costs_no_morale(self):
        bf, arch, tgt = self._defender("wall")
        m0 = tgt.morale
        ai.attack(bf, arch.soldiers[0], arch, tgt.soldiers[0], _Max())
        self.assertEqual(tgt.morale, m0, "the anchor shrugs the flank off")

        bf2, arch2, tgt2 = self._defender("grass")
        m0 = tgt2.morale
        ai.attack(bf2, arch2.soldiers[0], arch2, tgt2.soldiers[0], _Max())
        self.assertLess(tgt2.morale, m0, "an open flank shakes them")


if __name__ == "__main__":
    unittest.main()
