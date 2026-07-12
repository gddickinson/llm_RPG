"""Elevation & high ground (P17.E1): the advantage of being above."""

import unittest

from engine.battle import BattleField, Squad
from engine.battle import battle_ai as ai
from engine.battle import battle_terrain as terrain


class _Max:
    def randint(self, a, b):
        return b


class _Fixed:
    def __init__(self, roll):
        self.roll = roll

    def randint(self, a, b):
        return self.roll if b == 20 else 0


class TestElevationLayer(unittest.TestCase):
    def test_set_get_default(self):
        bf = BattleField(10, 10)
        self.assertEqual(bf.elevation_at(3, 3), 0)      # flat by default
        bf.set_elevation(3, 3, 2)
        self.assertEqual(bf.elevation_at(3, 3), 2)
        bf.set_elevation(3, 3, 0)                        # 0 clears it
        self.assertNotIn((3, 3), bf.elevation)

    def test_round_trips(self):
        bf = BattleField(8, 8)
        bf.set_elevation(2, 2, 3)
        bf.set_elevation(5, 1, -1)
        clone = BattleField.from_dict(bf.to_dict())
        self.assertEqual(clone.elevation_at(2, 2), 3)
        self.assertEqual(clone.elevation_at(5, 1), -1)


class TestHeightMath(unittest.TestCase):
    def _bf(self, atk_lv, def_lv):
        bf = BattleField(12, 12)
        bf.set_elevation(7, 6, atk_lv)
        bf.set_elevation(6, 6, def_lv)
        return bf

    def test_to_hit_up_and_down(self):
        self.assertEqual(terrain.height_to_hit(self._bf(2, 0),
                                               (7, 6), (6, 6)), 2)   # downhill
        self.assertEqual(terrain.height_to_hit(self._bf(0, 2),
                                               (7, 6), (6, 6)), -2)  # uphill
        self.assertEqual(terrain.height_to_hit(self._bf(0, 0),
                                               (7, 6), (6, 6)), 0)
        self.assertEqual(terrain.height_to_hit(self._bf(9, 0),
                                               (7, 6), (6, 6)),
                         terrain.MAX_TO_HIT)                        # capped

    def test_charge_momentum(self):
        self.assertGreater(terrain.charge_dmg_mult(self._bf(2, 0),
                                                   (7, 6), (6, 6)), 1.0)
        self.assertLess(terrain.charge_dmg_mult(self._bf(0, 2),
                                                (7, 6), (6, 6)), 1.0)
        self.assertEqual(terrain.charge_dmg_mult(self._bf(0, 0),
                                                 (7, 6), (6, 6)), 1.0)

    def test_height_extends_reach(self):
        bf = BattleField(12, 12)
        bf.set_elevation(5, 5, 2)
        self.assertEqual(terrain.height_reach(bf, (5, 5)), 2)
        self.assertEqual(terrain.height_reach(bf, (0, 0)), 0)


class TestInBattle(unittest.TestCase):
    def _duel(self, atk_lv, def_lv):
        bf = BattleField(14, 14)
        atk = Squad.raise_squad("a", "red", "infantry_sword", [(7, 6)])
        tgt = Squad.raise_squad("t", "blue", "infantry_sword", [(6, 6)])
        tgt.soldiers[0].facing = (1, 0)         # faces the attacker (front)
        bf.set_elevation(7, 6, atk_lv)
        bf.set_elevation(6, 6, def_lv)
        bf.add_squad(atk)
        bf.add_squad(tgt)
        return bf, atk, tgt

    def test_downhill_lands_where_flat_misses(self):
        # a marginal roll: the height edge is what carries it home
        bf, atk, tgt = self._duel(atk_lv=2, def_lv=0)
        hp0 = tgt.soldiers[0].hp
        ai.attack(bf, atk.soldiers[0], atk, tgt.soldiers[0], _Fixed(6))
        self.assertLess(tgt.soldiers[0].hp, hp0, "downhill lands")

        bf2, atk2, tgt2 = self._duel(atk_lv=0, def_lv=0)   # flat, same roll
        hp0 = tgt2.soldiers[0].hp
        ai.attack(bf2, atk2.soldiers[0], atk2, tgt2.soldiers[0], _Fixed(6))
        self.assertEqual(tgt2.soldiers[0].hp, hp0, "flat glances off")

    def test_high_ground_shoots_farther(self):
        # one tile beyond this archer's own flat reach (P17.9 per-unit
        # range: the longbow already outreaches the base 5)
        bf = BattleField(30, 12)
        arch = Squad.raise_squad("a", "red", "archer_longbow", [(5, 6)])
        far = ai.ranged_reach(arch) + 1
        tgt = Squad.raise_squad("t", "blue", "infantry_sword",
                                [(5 + far, 6)])
        bf.add_squad(arch)
        bf.add_squad(tgt)
        # flat: out of range, no shot
        hp0 = tgt.soldiers[0].hp
        ai.attack(bf, arch.soldiers[0], arch, tgt.soldiers[0], _Max())
        self.assertEqual(tgt.soldiers[0].hp, hp0)
        # from a hill: the extra tile of range reaches
        bf.set_elevation(5, 6, 2)
        ai.attack(bf, arch.soldiers[0], arch, tgt.soldiers[0], _Max())
        self.assertLess(tgt.soldiers[0].hp, hp0, "the high archer reaches")


if __name__ == "__main__":
    unittest.main()
