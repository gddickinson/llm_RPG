"""Formations I (P17.16): line & loose, with cohesion."""

import unittest

from engine.battle import BattleField, Squad
from engine.battle import battle_formation as form
from engine.battle import battle_ai as ai


class _Max:
    def randint(self, a, b):
        return b


def _line(formation="line"):
    """A tight vertical file of four, all facing east — so each man's
    right hand (south) rests on the next (shield overlap)."""
    bf = BattleField(24, 16)
    sq = Squad.raise_squad("L", "blue", "infantry_sword",
                           [(5, 5), (5, 6), (5, 7), (5, 8)])
    for s in sq.soldiers:
        s.facing = (1, 0)
    sq.formation = formation
    bf.add_squad(sq)
    return bf, sq


class TestCohesion(unittest.TestCase):
    def test_a_tight_uniform_line_is_cohesive(self):
        bf, sq = _line()
        self.assertEqual(form.cohesion(bf, sq), 1.0)
        self.assertFalse(form.is_broken(bf, sq))

    def test_split_facings_break_it(self):
        bf, sq = _line()
        for s, f in zip(sq.soldiers, [(1, 0), (-1, 0), (0, 1), (0, -1)]):
            s.facing = f                       # no common direction
        self.assertLess(form.cohesion(bf, sq), 0.5)
        self.assertTrue(form.is_broken(bf, sq))

    def test_none_formation_never_breaks(self):
        bf, sq = _line(formation=None)
        self.assertFalse(form.is_broken(bf, sq))

    def test_empty_squad_zero(self):
        bf, sq = _line()
        for s in sq.soldiers:
            s.alive = False
        self.assertEqual(form.cohesion(bf, sq), 0.0)


class TestEffects(unittest.TestCase):
    def test_line_is_half_speed(self):
        _, line = _line("line")
        _, loose = _line("loose")
        _, open_ = _line(None)
        self.assertEqual(form.speed_mult(line), 0.5)
        self.assertEqual(form.speed_mult(loose), 1.0)
        self.assertEqual(form.speed_mult(open_), 1.0)

    def test_loose_halves_incoming_missiles(self):
        _, loose = _line("loose")
        _, line = _line("line")
        self.assertEqual(form.incoming_ranged_mult(loose), 0.5)
        self.assertEqual(form.incoming_ranged_mult(line), 1.0)

    def test_line_shield_overlap_front_only(self):
        bf, line = _line("line")
        top = line.soldiers[0]                 # (5,5), right-mate (5,6) stands
        # attacker due east = the front arc
        east = Squad.raise_squad("E", "red", "infantry_sword", [(6, 5)])
        bf.add_squad(east)
        self.assertEqual(form.defense_bonus(bf, line, top, east.soldiers[0]), 2)
        # attacker due north = a flank — no shield help
        north = Squad.raise_squad("N", "red", "infantry_sword", [(5, 4)])
        bf.add_squad(north)
        self.assertEqual(form.defense_bonus(bf, line, top, north.soldiers[0]), 0)

    def test_no_bonus_without_a_right_mate(self):
        bf, line = _line("line")
        bottom = line.soldiers[3]              # (5,8), nobody at (5,9)
        east = Squad.raise_squad("E", "red", "infantry_sword", [(6, 8)])
        bf.add_squad(east)
        self.assertEqual(form.defense_bonus(bf, line, bottom,
                                            east.soldiers[0]), 0)

    def test_broken_line_loses_its_shield(self):
        bf, line = _line("line")
        for s, f in zip(line.soldiers, [(1, 0), (-1, 0), (0, 1), (0, -1)]):
            s.facing = f                       # break cohesion
        top = line.soldiers[0]
        east = Squad.raise_squad("E", "red", "infantry_sword", [(6, 5)])
        bf.add_squad(east)
        top.facing = (1, 0)                    # still faces the attacker
        self.assertEqual(form.defense_bonus(bf, line, top,
                                            east.soldiers[0]), 0)

    def test_steady_rewards_a_deep_cohesive_line(self):
        _, line = _line("line")
        self.assertGreater(form.steady(_line("line")[0], line), 0)
        _, loose = _line("loose")
        self.assertEqual(form.steady(_line("loose")[0], loose), 0)


class TestVolleyIntegration(unittest.TestCase):
    def _shoot(self, formation):
        bf = BattleField(24, 16)
        tgt = Squad.raise_squad("t", "blue", "infantry_sword", [(5, 5)])
        tgt.formation = formation
        arch = Squad.raise_squad("a", "red", "archer_longbow", [(10, 5)])
        bf.add_squad(tgt)
        bf.add_squad(arch)
        t = tgt.soldiers[0]
        hp0 = t.hp
        ai.attack(bf, arch.soldiers[0], arch, t, _Max())
        return hp0 - t.hp

    def test_loose_takes_half_a_volley(self):
        self.assertLess(self._shoot("loose"), self._shoot(None))


class TestBreakAndPersistence(unittest.TestCase):
    def test_break_shocks_morale_once(self):
        bf, line = _line("line")
        self.assertFalse(form.check_break(bf, line))     # cohesive, no break
        for s, f in zip(line.soldiers, [(1, 0), (-1, 0), (0, 1), (0, -1)]):
            s.facing = f
        m0 = line.morale
        self.assertTrue(form.check_break(bf, line))      # it comes apart
        self.assertEqual(line.morale, m0 - 4)
        self.assertFalse(form.check_break(bf, line))     # no second shock
        self.assertEqual(line.morale, m0 - 4)

    def test_formation_state_round_trips(self):
        _, line = _line("line")
        line.formation_broken = True
        clone = Squad.from_dict(line.to_dict())
        self.assertEqual(clone.formation, "line")
        self.assertTrue(clone.formation_broken)


if __name__ == "__main__":
    unittest.main()
