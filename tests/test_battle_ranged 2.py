"""Ranged fidelity (P17.9): per-unit range, reload cadence, and the
move-and-shoot accuracy penalty (with the horse-archer exemption)."""

import unittest

from engine.battle import BattleField, Squad, BattleSession
from engine.battle import battle_ai as ai


class _Max:                      # every d20 comes up 20 → always hits
    def randint(self, a, b):
        return b

    def random(self):
        return 0.0


class _Min:                      # every roll is the floor
    def randint(self, a, b):
        return a

    def random(self):
        return 1.0


def _sq(archetype, cells, team="red", sid="s"):
    return Squad.raise_squad(sid, team, archetype, cells)


class TestPerUnitRange(unittest.TestCase):
    def test_range_factor_scales_reach(self):
        long_ = _sq("archer_longbow", [(0, 0)])
        cross = _sq("archer_crossbow", [(0, 0)])
        base = _sq("archer_fire", [(0, 0)])        # no range_factor -> 1.0
        self.assertGreater(ai.ranged_reach(long_), ai.ranged_reach(cross))
        self.assertGreater(ai.ranged_reach(cross), ai.ranged_reach(base))

    def test_longbow_outreaches_the_base_archer(self):
        # a target sits beyond the base 5 but inside the longbow's reach
        far = ai.RANGED_REACH + 2
        bf = BattleField(30, 6)
        bow = _sq("archer_longbow", [(2, 3)])
        tgt = _sq("infantry_sword", [(2 + far, 3)], team="blue", sid="t")
        bf.add_squad(bow)
        bf.add_squad(tgt)
        hp0 = tgt.soldiers[0].hp
        self.assertTrue(
            ai.attack(bf, bow.soldiers[0], bow, tgt.soldiers[0], _Max())
            or tgt.soldiers[0].hp < hp0,
            "the longbow reaches a foe the base archer could not")

    def test_out_of_range_is_no_shot(self):
        bf = BattleField(40, 6)
        bow = _sq("archer_longbow", [(2, 3)])
        tgt = _sq("infantry_sword", [(2 + ai.ranged_reach(bow) + 3, 3)],
                  team="blue", sid="t")
        bf.add_squad(bow)
        bf.add_squad(tgt)
        hp0 = tgt.soldiers[0].hp
        ai.attack(bf, bow.soldiers[0], bow, tgt.soldiers[0], _Max())
        self.assertEqual(tgt.soldiers[0].hp, hp0)


class TestReload(unittest.TestCase):
    def test_crossbow_arms_a_reload_after_loosing(self):
        bf = BattleField(12, 6)
        xbow = _sq("archer_crossbow", [(2, 3)])
        tgt = _sq("infantry_sword", [(5, 3)], team="blue", sid="t")
        bf.add_squad(xbow)
        bf.add_squad(tgt)
        s = xbow.soldiers[0]
        self.assertEqual(s.reload_left, 0)
        ai.attack(bf, s, xbow, tgt.soldiers[0], _Max())
        self.assertGreater(s.reload_left, 0, "the bolt loosed; now reloading")

    def test_reloading_crossbow_holds_its_shot(self):
        bf = BattleField(12, 6)
        xbow = _sq("archer_crossbow", [(2, 3)])
        tgt = _sq("infantry_sword", [(5, 3)], team="blue", sid="t")
        bf.add_squad(xbow)
        bf.add_squad(tgt)
        s = xbow.soldiers[0]
        ai.attack(bf, s, xbow, tgt.soldiers[0], _Max())   # first bolt
        hp1 = tgt.soldiers[0].hp
        # immediately again, still loading -> no shot lands
        ai.attack(bf, s, xbow, tgt.soldiers[0], _Max())
        self.assertEqual(tgt.soldiers[0].hp, hp1, "can't fire mid-reload")

    def test_longbow_reloads_instantly(self):
        # reload 0 -> never gated; fires on back-to-back calls
        bf = BattleField(12, 6)
        bow = _sq("archer_longbow", [(2, 3)])
        tgt = _sq("infantry_sword", [(4, 3)], team="blue", sid="t")
        bf.add_squad(bow)
        bf.add_squad(tgt)
        s = bow.soldiers[0]
        ai.attack(bf, s, bow, tgt.soldiers[0], _Max())
        self.assertEqual(s.reload_left, 0)
        hp1 = tgt.soldiers[0].hp
        ai.attack(bf, s, bow, tgt.soldiers[0], _Max())
        self.assertLess(tgt.soldiers[0].hp, hp1, "the longbow looses again")

    def test_reload_ticks_down_over_a_battle(self):
        # over a run the crossbow fires strictly less often than a longbow
        def shots(archetype):
            bf = BattleField(16, 12)
            a = _sq(archetype, [(2, 5)])
            a.order = "hold"                 # stand and shoot, don't close
            # a deep, stationary block of bodies so it never runs dry and
            # the archer never has to move (no move-and-shoot muddle)
            block = [(x, y) for x in range(6, 9) for y in range(3, 9)]
            t = _sq("infantry_pike", block, team="blue", sid="t")
            t.order = "hold"
            bf.add_squad(a)
            bf.add_squad(t)
            sess = BattleSession(bf, seed=1)
            fired = 0
            for _ in range(14):
                sess.tick()
                fired += len(sess.tracers)
            return fired
        self.assertLess(shots("archer_crossbow"), shots("archer_longbow"),
                        "the crossbow's reload thins its volume of fire")


class TestMoveAndShoot(unittest.TestCase):
    def _hit_rate(self, moved, parthian_archetype="archer_longbow"):
        bf = BattleField(16, 6)
        bow = _sq(parthian_archetype, [(2, 3)])
        tgt = _sq("infantry_sword", [(6, 3)], team="blue", sid="t")
        bf.add_squad(bow)
        bf.add_squad(tgt)
        s = bow.soldiers[0]
        hits = 0
        n = 200
        for i in range(n):
            s.moved_last = moved
            s.reload_left = 0
            tgt.soldiers[0].hp = tgt.soldiers[0].max_hp
            # a middling deterministic roll so the -4 penalty can matter
            class _R:
                def __init__(self, v):
                    self.v = v

                def randint(self, a, b):
                    return min(b, a + (self.v % (b - a + 1)))
            landed = ai.attack(bf, s, bow, tgt.soldiers[0], _R(i))
            if tgt.soldiers[0].hp < tgt.soldiers[0].max_hp:
                hits += 1
        return hits

    def test_shooting_on_the_move_is_less_accurate(self):
        still = self._hit_rate(False)
        moving = self._hit_rate(True)
        self.assertLess(moving, still,
                        "loosing on the move should miss more often")

    def test_horse_archer_ignores_the_move_penalty(self):
        still = self._hit_rate(False, "cavalry_mounted_archer")
        moving = self._hit_rate(True, "cavalry_mounted_archer")
        self.assertEqual(moving, still,
                         "the Parthian shot fires accurately on the move")


class TestPersistence(unittest.TestCase):
    def test_reload_and_moved_round_trip(self):
        bf = BattleField(10, 6)
        sq = _sq("archer_crossbow", [(3, 3)])
        bf.add_squad(sq)
        sq.soldiers[0].reload_left = 2
        sq.soldiers[0].moved_last = True
        clone = BattleField.from_dict(bf.to_dict())
        cs = clone.squads[sq.squad_id].soldiers[0]
        self.assertEqual(cs.reload_left, 2)
        self.assertTrue(cs.moved_last)


if __name__ == "__main__":
    unittest.main()
