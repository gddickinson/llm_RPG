"""Combined arms (P17.18): the hammer-and-anvil rout trigger, and the
wedge that breaches a line."""

import unittest

from engine.battle import BattleField, Squad
from engine.battle import battle_ai as ai
from engine.battle import battle_formation as form


class _Max:
    def randint(self, a, b):
        return b


class _Fixed:
    """A fixed d20 roll (and no damage-jitter)."""
    def __init__(self, roll):
        self.roll = roll

    def randint(self, a, b):
        return self.roll if b == 20 else 0


class TestHammerAndAnvil(unittest.TestCase):
    def _target_east(self):
        bf = BattleField(16, 16)
        tgt = Squad.raise_squad("t", "blue", "infantry_sword", [(6, 6)])
        tgt.soldiers[0].facing = (1, 0)          # faces east
        return bf, tgt

    def test_pinned_then_flanked_is_a_rout_trigger(self):
        bf, tgt = self._target_east()
        anvil = Squad.raise_squad("anvil", "red", "infantry_sword",
                                  [(7, 6)])        # on the FRONT (east)
        hammer = Squad.raise_squad("hammer", "red", "infantry_sword",
                                   [(6, 5)])       # on the FLANK (north)
        bf.add_squad(tgt)
        bf.add_squad(anvil)
        bf.add_squad(hammer)
        m0 = tgt.morale
        ai.attack(bf, hammer.soldiers[0], hammer, tgt.soldiers[0], _Max())
        self.assertLessEqual(tgt.morale, m0 - 8)   # flank(-2) + anvil(-6)

    def test_a_flank_without_a_pin_is_just_a_flank(self):
        bf, tgt = self._target_east()
        hammer = Squad.raise_squad("hammer", "red", "infantry_sword",
                                   [(6, 5)])       # flank only, no anvil
        bf.add_squad(tgt)
        bf.add_squad(hammer)
        m0 = tgt.morale
        ai.attack(bf, hammer.soldiers[0], hammer, tgt.soldiers[0], _Max())
        self.assertEqual(tgt.morale, m0 - 2)

    def test_one_squad_enveloping_is_not_hammer_and_anvil(self):
        # the RPS-preserving case: a single squad on the front AND flank
        # is envelopment (its own damage bonus), not two coordinated
        # forces — so no extra rout morale.
        bf, tgt = self._target_east()
        enve = Squad.raise_squad("e", "red", "infantry_sword",
                                 [(7, 6), (6, 5)])   # front + flank, ONE squad
        bf.add_squad(tgt)
        bf.add_squad(enve)
        m0 = tgt.morale
        ai.attack(bf, enve.soldiers[1], enve, tgt.soldiers[0], _Max())
        self.assertEqual(tgt.morale, m0 - 2)       # just the flank


class TestWedge(unittest.TestCase):
    def test_wedge_charge_bonus(self):
        sq = Squad.raise_squad("w", "red", "cavalry_light", [(1, 1)])
        self.assertEqual(form.wedge_charge_bonus(sq), 0)
        sq.formation = "wedge"
        self.assertEqual(form.wedge_charge_bonus(sq), 3)

    def _charge(self, wedge):
        bf = BattleField(16, 16)
        line = Squad.raise_squad("L", "blue", "infantry_sword", [(6, 6)])
        line.soldiers[0].facing = (-1, 0)          # faces the charger (front)
        line.soldiers[0].hp = 1                     # a hit = a kill = overrun
        cav = Squad.raise_squad("C", "red", "cavalry_light", [(5, 6)])
        if wedge:
            cav.formation = "wedge"
        bf.add_squad(line)
        bf.add_squad(cav)
        return ai.charge_attack(bf, cav.soldiers[0], cav,
                                line.soldiers[0], line, _Fixed(4))

    def test_wedge_breaches_where_a_line_charge_stalls(self):
        self.assertEqual(self._charge(wedge=True), "overrun")
        self.assertNotEqual(self._charge(wedge=False), "overrun")

    def test_wedge_gets_no_defensive_bonus(self):
        wedge = Squad.raise_squad("w", "blue", "infantry_sword", [(1, 1)])
        wedge.formation = "wedge"
        self.assertEqual(form.speed_mult(wedge), 1.0)         # not slowed
        self.assertEqual(form.incoming_ranged_mult(wedge), 1.0)
        self.assertEqual(form.attack_penalty(wedge), 0)


if __name__ == "__main__":
    unittest.main()
