"""Doctrine AI (P17.19): brace when a charge is coming, commit a reserve
where the fight is already won."""

import unittest

from engine.battle import BattleField, Squad, BattleSession
from engine.battle import battle_doctrine as doc


def _at(x, y, n=4, dx=0, dy=1):
    return [(x + dx * i, y + dy * i) for i in range(n)]


class TestBrace(unittest.TestCase):
    def _field(self, charger_x):
        bf = BattleField(40, 20)
        spear = Squad.raise_squad("s", "blue", "infantry_spear",
                                  _at(10, 8))
        cav = Squad.raise_squad("c", "red", "cavalry_heavy",
                                _at(charger_x, 8))
        bf.add_squad(spear)
        bf.add_squad(cav)
        return bf, spear

    def test_sees_the_charge_and_braces(self):
        bf, spear = self._field(14)                # cavalry 4 tiles off
        self.assertIsNotNone(doc.incoming_charger(bf, spear))
        self.assertTrue(doc.should_brace(bf, spear))
        doc.apply(bf, spear)
        self.assertTrue(spear.braced)

    def test_no_charger_stands_the_hedge_down(self):
        bf, spear = self._field(34)                # cavalry far away
        spear.braced = True
        self.assertIsNone(doc.incoming_charger(bf, spear))
        doc.apply(bf, spear)
        self.assertFalse(spear.braced)

    def test_only_pike_and_spear_brace(self):
        bf = BattleField(40, 20)
        swords = Squad.raise_squad("sw", "blue", "infantry_sword",
                                   _at(10, 8))
        cav = Squad.raise_squad("c", "red", "cavalry_heavy", _at(13, 8))
        bf.add_squad(swords)
        bf.add_squad(cav)
        self.assertFalse(doc.should_brace(bf, swords))   # not brace-capable

    def test_infantry_is_not_a_charger(self):
        bf = BattleField(40, 20)
        spear = Squad.raise_squad("s", "blue", "infantry_spear", _at(10, 8))
        foot = Squad.raise_squad("f", "red", "infantry_sword", _at(13, 8))
        bf.add_squad(spear)
        bf.add_squad(foot)
        self.assertIsNone(doc.incoming_charger(bf, spear))


class TestCommit(unittest.TestCase):
    def _reserve(self, order="hold", enemy_n=2, enemy_x=16, ally=True):
        bf = BattleField(40, 20)
        res = Squad.raise_squad("r", "blue", "infantry_sword", _at(10, 8))
        res.order = order
        if ally:
            bf.add_squad(Squad.raise_squad("a", "blue", "infantry_sword",
                                           _at(8, 8)))
        bf.add_squad(res)
        bf.add_squad(Squad.raise_squad("e", "red", "infantry_sword",
                                       _at(enemy_x, 8, n=enemy_n)))
        return bf, res

    def test_local_advantage(self):
        bf, res = self._reserve()
        self.assertGreater(doc.local_advantage(bf, res), 1.0)

    def test_commits_where_it_wins(self):
        bf, res = self._reserve()
        self.assertTrue(doc.should_commit(bf, res))
        doc.apply(bf, res)
        self.assertEqual(res.order, "charge")

    def test_will_not_commit_when_already_charging(self):
        bf, res = self._reserve(order="charge")
        self.assertFalse(doc.should_commit(bf, res))

    def test_will_not_commit_when_outnumbered(self):
        # a lone squad against a bigger force nearby — no advantage
        bf, res = self._reserve(ally=False, enemy_n=10, enemy_x=14)
        self.assertLess(doc.local_advantage(bf, res), doc.ADVANTAGE)
        self.assertFalse(doc.should_commit(bf, res))

    def test_will_not_commit_when_already_engaged(self):
        bf, res = self._reserve(enemy_x=11)          # enemy adjacent already
        self.assertFalse(doc.should_commit(bf, res))


class TestIntegration(unittest.TestCase):
    def test_a_spear_line_braces_in_a_live_battle(self):
        bf = BattleField(40, 20)
        spear = Squad.raise_squad("s", "blue", "infantry_spear", _at(18, 8))
        spear.order = "hold"
        cav = Squad.raise_squad("c", "red", "cavalry_heavy", _at(22, 8))
        cav.set_order("charge", "s")
        bf.add_squad(spear)
        bf.add_squad(cav)
        BattleSession(bf, seed=1).tick()
        self.assertTrue(spear.braced, "the AI set to receive the charge")


if __name__ == "__main__":
    unittest.main()
