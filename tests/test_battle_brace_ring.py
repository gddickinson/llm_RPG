"""Bracing & the all-facing ring (P17.17): pikes must be SET TO RECEIVE
to stop a charge, and an orbis/schiltron shows its front to every side."""

import unittest

from engine.battle import BattleField, Squad
from engine.battle import battle_ai as ai
from engine.battle import battle_formation as form


class _Max:
    def randint(self, a, b):
        return b


class TestBrace(unittest.TestCase):
    def _charge(self, order, braced=False, hp=None):
        bf = BattleField(16, 16)
        spear = Squad.raise_squad("s", "blue", "infantry_spear", [(6, 6)])
        cav = Squad.raise_squad("c", "red", "cavalry_heavy", [(5, 6)])
        spear.order = order
        spear.braced = braced
        if hp is not None:
            spear.soldiers[0].hp = hp
        bf.add_squad(spear)
        bf.add_squad(cav)
        return ai.charge_attack(bf, cav.soldiers[0], cav,
                                spear.soldiers[0], spear, _Max())

    def test_braced_spear_on_hold_stops_the_charge(self):
        self.assertIn(self._charge("hold"), ("stopped", "repelled"))

    def test_unbraced_spear_is_trampled(self):
        # ordered to charge, not braced -> the hedge is just infantry
        self.assertEqual(self._charge("charge", braced=False, hp=1),
                         "overrun")

    def test_the_brace_flag_restores_the_hedge_while_moving(self):
        self.assertIn(self._charge("move", braced=True),
                      ("stopped", "repelled"))

    def test_is_braced_helper(self):
        sq = Squad.raise_squad("x", "blue", "infantry_spear", [(1, 1)])
        sq.order = "hold"
        self.assertTrue(ai._is_braced(sq))
        sq.order = "charge"
        self.assertFalse(ai._is_braced(sq))
        sq.braced = True
        self.assertTrue(ai._is_braced(sq))


class TestRingArc(unittest.TestCase):
    def test_effective_arc_flattens_to_front(self):
        ring = Squad.raise_squad("r", "blue", "infantry_sword", [(6, 6)])
        ring.formation = "ring"
        for base in ("front", "flank", "rear"):
            self.assertEqual(form.effective_arc(ring, base), "front")
        ring.formation = None
        self.assertEqual(form.effective_arc(ring, "rear"), "rear")

    def _rear_mods(self, formation):
        bf = BattleField(14, 14)
        tgt = Squad.raise_squad("t", "blue", "infantry_sword", [(6, 6)])
        tgt.formation = formation
        atk = Squad.raise_squad("a", "red", "infantry_sword", [(5, 6)])
        bf.add_squad(tgt)
        bf.add_squad(atk)
        tgt.soldiers[0].facing = (1, 0)          # attacker to the west = rear
        return ai._position_mods(bf, atk.soldiers[0], tgt.soldiers[0])

    def test_ring_denies_the_rear_bonus(self):
        self.assertEqual(self._rear_mods("ring"), (0, 1.0))    # all front
        self.assertEqual(self._rear_mods(None), (4, 1.5))      # exposed rear

    def test_ring_ignores_a_rear_morale_hit(self):
        for formation, drops in ((None, True), ("ring", False)):
            bf = BattleField(14, 14)
            tgt = Squad.raise_squad("t", "blue", "infantry_sword", [(6, 6)])
            tgt.formation = formation
            atk = Squad.raise_squad("a", "red", "infantry_sword", [(5, 6)])
            bf.add_squad(tgt)
            bf.add_squad(atk)
            tgt.soldiers[0].facing = (1, 0)      # rear attacker
            m0 = tgt.morale
            ai.attack(bf, atk.soldiers[0], atk, tgt.soldiers[0], _Max())
            if drops:
                self.assertLess(tgt.morale, m0)
            else:
                self.assertEqual(tgt.morale, m0)


class TestRingCosts(unittest.TestCase):
    def test_ring_is_slow_and_missile_vulnerable(self):
        sq = Squad.raise_squad("r", "blue", "infantry_sword", [(1, 1)])
        sq.formation = "ring"
        self.assertEqual(form.speed_mult(sq), 0.5)
        self.assertGreater(form.incoming_ranged_mult(sq), 1.0)   # Falkirk
        self.assertEqual(form.attack_penalty(sq), -2)

    def test_brace_round_trips(self):
        sq = Squad.raise_squad("r", "blue", "infantry_spear", [(1, 1)])
        sq.braced = True
        sq.formation = "ring"
        clone = Squad.from_dict(sq.to_dict())
        self.assertTrue(clone.braced)
        self.assertEqual(clone.formation, "ring")


if __name__ == "__main__":
    unittest.main()
