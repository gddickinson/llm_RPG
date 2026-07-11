"""Charge & overrun (P17.13): charging cavalry (and huge beasts)
trample loose infantry but shatter on braced spears/pikes."""

import collections
import random
import unittest

from engine.battle import BattleField, BattleSession, Squad
from engine.battle.battle_ai import charge_attack, _shove
from engine.battle.battle_scenario import build_field


def _fresh(att, deft):
    bf = BattleField(12, 8)
    a = Squad.raise_squad("a", "red", att, [(5, 4)])
    d = Squad.raise_squad("d", "blue", deft, [(6, 4)])
    bf.add_squad(a)
    bf.add_squad(d)
    return bf, a.soldiers[0], a, d.soldiers[0], d


def _duel(att, deft, n=10, seeds=12):
    o = collections.Counter()
    for seed in range(seeds):
        bf = BattleField(40, 16)
        a = Squad.raise_squad("a", "red", att,
                              [(6, 4 + i) for i in range(n)])
        d = Squad.raise_squad("d", "blue", deft,
                              [(30, 4 + i) for i in range(n)])
        a.set_order("charge", "d")
        d.set_order("hold", "a")
        bf.add_squad(a)
        bf.add_squad(d)
        o[BattleSession(bf, seed=seed).run_headless(max_ticks=300)[
            "winner"]] += 1
    return o


class TestChargeCapability(unittest.TestCase):
    def test_charge_bonus_property(self):
        cav = Squad.raise_squad("c", "red", "cavalry_light", [(0, 0)])
        foot = Squad.raise_squad("f", "red", "infantry_sword", [(0, 0)])
        ele = Squad.raise_squad("e", "red", "war_elephant", [(0, 0)])
        self.assertGreater(cav.charge_bonus, 1)
        self.assertEqual(foot.charge_bonus, 1.0)
        self.assertGreater(ele.charge_bonus, 1)      # beasts trample


class TestChargeResolution(unittest.TestCase):
    def test_never_overruns_braced_spears(self):
        for kind in ("infantry_spear", "infantry_pike"):
            for seed in range(40):
                bf, aso, asq, dso, dsq = _fresh("cavalry_light", kind)
                res = charge_attack(bf, aso, asq, dso, dsq,
                                    random.Random(seed))
                self.assertIn(res, ("stopped", "repelled"),
                              f"{kind} must not be overrun")

    def test_overruns_loose_infantry_more_often_than_not(self):
        overruns = 0
        for seed in range(80):
            bf, aso, asq, dso, dsq = _fresh("cavalry_heavy",
                                            "infantry_sword")
            if charge_attack(bf, aso, asq, dso, dsq,
                             random.Random(seed)) == "overrun":
                overruns += 1
        self.assertGreater(overruns, 40, "horse should trample foot")

    def test_shove_clears_the_lane(self):
        bf = BattleField(12, 8)
        vic = Squad.raise_squad("v", "blue", "infantry_sword", [(6, 4)])
        chg = Squad.raise_squad("c", "red", "cavalry_light", [(5, 4)])
        bf.add_squad(vic)
        bf.add_squad(chg)
        victim, charger = vic.soldiers[0], chg.soldiers[0]
        self.assertTrue(_shove(bf, victim, charger))
        self.assertGreater(
            max(abs(victim.x - charger.x), abs(victim.y - charger.y)), 1,
            "the footman was barged clear of the charger")


class TestChargeInBattle(unittest.TestCase):
    def test_cavalry_overruns_a_sword_line(self):
        o = _duel("cavalry_light", "infantry_sword")
        self.assertGreaterEqual(o["red"], 10, "horse rides down foot")

    def test_spears_and_pikes_stop_cavalry(self):
        self.assertGreaterEqual(_duel("cavalry_light", "infantry_spear")[
            "blue"], 10, "spears blunt the charge")
        self.assertGreaterEqual(_duel("cavalry_light", "infantry_pike")[
            "blue"], 10, "pikes shatter it")

    def test_beasts_trample_loose_infantry(self):
        self.assertGreaterEqual(_duel("war_elephant", "infantry_sword",
                                      n=6)["red"], 7,
                                "elephants trample too")

    def test_cavalry_charge_scenario_is_won_by_the_horse(self):
        r = BattleSession(build_field("cavalry_charge"),
                          seed=0).run_headless(max_ticks=300)
        self.assertEqual(r["winner"], "red")


if __name__ == "__main__":
    unittest.main()
