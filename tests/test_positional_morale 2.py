"""Positional morale (P17.15): flanking, being surrounded, a routed
neighbour, and running down the broken all press the morale bar — so
position pays in decisions, not just damage."""

import unittest

from engine.battle import BattleField, Squad
from engine.battle import battle_ai as ai


class _MaxRng:
    """Always rolls the top of the range — a guaranteed hit."""
    def randint(self, a, b):
        return b


def _pair(target_facing):
    bf = BattleField(14, 14)
    tgt = Squad.raise_squad("t", "blue", "infantry_sword", [(6, 6)])
    atk = Squad.raise_squad("a", "red", "infantry_sword", [(7, 6)])  # due east
    bf.add_squad(tgt)
    bf.add_squad(atk)
    tgt.soldiers[0].facing = target_facing
    return bf, atk, atk.soldiers[0], tgt


class TestFlankMorale(unittest.TestCase):
    def test_a_rear_blow_shakes_the_squad(self):
        bf, atk, a, tgt = _pair((-1, 0))          # east is the rear
        m0 = tgt.morale
        ai.attack(bf, a, atk, tgt.soldiers[0], _MaxRng())
        self.assertLess(tgt.morale, m0)

    def test_a_front_blow_costs_no_morale(self):
        bf, atk, a, tgt = _pair((1, 0))           # east is the front
        m0 = tgt.morale
        ai.attack(bf, a, atk, tgt.soldiers[0], _MaxRng())
        self.assertEqual(tgt.morale, m0)

    def test_rear_shakes_more_than_flank(self):
        bf, atk, a, rear = _pair((-1, 0))
        r0 = rear.morale
        ai.attack(bf, a, atk, rear.soldiers[0], _MaxRng())
        rear_drop = r0 - rear.morale
        bf2, atk2, a2, flank = _pair((0, -1))     # east is a flank
        f0 = flank.morale
        ai.attack(bf2, a2, atk2, flank.soldiers[0], _MaxRng())
        self.assertGreater(rear_drop, f0 - flank.morale)


class TestSurroundedMorale(unittest.TestCase):
    def _boxed(self, positions):
        bf = BattleField(20, 20)
        tgt = Squad.raise_squad("t", "blue", "infantry_sword", positions)
        foes = Squad.raise_squad("e", "red", "infantry_sword",
                                 [(7, 6), (5, 6), (6, 7), (6, 5)])
        bf.add_squad(tgt)
        bf.add_squad(foes)
        return bf, tgt

    def test_a_hemmed_in_squad_loses_nerve(self):
        bf, tgt = self._boxed([(6, 6)])           # its one man is boxed
        m0 = tgt.morale
        ai.update_morale(bf, tgt)
        self.assertLessEqual(tgt.morale, m0 - 4)

    def test_a_deep_squad_shrugs_off_a_few_trapped_men(self):
        deep = [(6, 6)] + [(2 + i, 2) for i in range(9)]   # 1 of 10 boxed
        bf, tgt = self._boxed(deep)
        m0 = tgt.morale
        ai.update_morale(bf, tgt)
        self.assertGreater(tgt.morale, m0 - 4, "depth resists")


class TestRunDown(unittest.TestCase):
    def test_a_routed_squad_is_struck_harder(self):
        bf = BattleField(12, 12)
        tgt = Squad.raise_squad("t", "blue", "infantry_sword", [(6, 6)])
        atk = Squad.raise_squad("a", "red", "infantry_sword", [(7, 6)])
        bf.add_squad(tgt)
        bf.add_squad(atk)
        tgt.soldiers[0].facing = (1, 0)           # front — no arc bonus
        base = ai._position_mods(bf, atk.soldiers[0], tgt.soldiers[0])
        tgt.routed = True
        run = ai._position_mods(bf, atk.soldiers[0], tgt.soldiers[0])
        self.assertGreater(run[0], base[0])       # easier to hit
        self.assertGreater(run[1], base[1])       # and hurts more


class TestRoutCascade(unittest.TestCase):
    def _drop_from_routed_ally(self, ally_pos):
        bf = BattleField(50, 50)
        sq = Squad.raise_squad("s", "blue", "infantry_sword", [(10, 10)])
        ally = Squad.raise_squad("a", "blue", "infantry_sword", [ally_pos])
        bf.add_squad(sq)
        bf.add_squad(ally)
        ally.routed = True
        m0 = sq.morale
        ai.update_morale(bf, sq)
        return m0 - sq.morale

    def test_a_close_rout_panics_more_than_a_distant_one(self):
        close = self._drop_from_routed_ally((12, 10))   # 2 tiles away
        far = self._drop_from_routed_ally((40, 40))      # far off
        self.assertGreater(close, far)
        self.assertGreater(close, 0)


if __name__ == "__main__":
    unittest.main()
