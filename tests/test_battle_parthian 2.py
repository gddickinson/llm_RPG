"""The Parthian shot (P17.20): a horse-archer looses over its shoulder
as it flees, and a routed squad keeps running (and shooting) every tick."""

import unittest

from engine.battle import BattleField, Squad, BattleSession
from engine.battle import battle_ai as ai


class TestCanParthian(unittest.TestCase):
    def test_only_the_horse_archer(self):
        ha = Squad.raise_squad("h", "blue", "cavalry_mounted_archer",
                               [(1, 1)])
        foot = Squad.raise_squad("s", "blue", "infantry_sword", [(1, 1)])
        bow = Squad.raise_squad("b", "blue", "archer_longbow", [(1, 1)])
        self.assertTrue(ai.can_parthian(ha))
        self.assertFalse(ai.can_parthian(foot))     # no ranged trick on foot
        self.assertFalse(ai.can_parthian(bow))       # a foot archer can't


class TestParthianShot(unittest.TestCase):
    def _fleeing(self, archetype, gap=2):
        bf = BattleField(30, 12)
        runner = Squad.raise_squad("r", "blue", archetype, [(12, 6)])
        runner.routed = True                         # already broken, fleeing
        foe = Squad.raise_squad("f", "red", "infantry_sword",
                                [(12 + gap, 6)])       # the pursuit
        bf.add_squad(runner)
        bf.add_squad(foe)
        return bf, runner, foe

    def test_a_fleeing_horse_archer_shoots_the_pursuer(self):
        bf, runner, foe = self._fleeing("cavalry_mounted_archer")
        hp0 = foe.soldiers[0].hp
        for _ in range(3):
            BattleSession(bf, seed=1).tick()
        self.assertLess(foe.soldiers[0].hp, hp0, "the Parthian shot bites")

    def test_it_flees_while_it_shoots(self):
        bf, runner, foe = self._fleeing("cavalry_mounted_archer")
        start = runner.soldiers[0].pos
        BattleSession(bf, seed=1).tick()
        self.assertNotEqual(runner.soldiers[0].pos, start, "it kept riding")

    def test_a_routed_foot_archer_only_runs(self):
        bf, runner, foe = self._fleeing("archer_longbow")
        hp0 = foe.soldiers[0].hp
        for _ in range(3):
            BattleSession(bf, seed=1).tick()
        self.assertEqual(foe.soldiers[0].hp, hp0, "foot can't shoot fleeing")


class TestRoutedFleesEveryTick(unittest.TestCase):
    def test_a_broken_squad_keeps_running(self):
        bf = BattleField(30, 12)
        broken = Squad.raise_squad("b", "blue", "infantry_sword", [(12, 6)])
        broken.routed = True
        foe = Squad.raise_squad("f", "red", "infantry_sword", [(6, 6)])
        bf.add_squad(broken)
        bf.add_squad(foe)
        sess = BattleSession(bf, seed=1)
        p0 = broken.soldiers[0].pos
        sess.tick()
        p1 = broken.soldiers[0].pos
        sess.tick()
        p2 = broken.soldiers[0].pos
        # it runs AWAY from the foe (to the east) every tick, not just once
        self.assertGreater(p1[0], p0[0])
        self.assertGreater(p2[0], p1[0])


if __name__ == "__main__":
    unittest.main()
