"""Facing, flanking & surround (P17.11): a blow from outside a man's
front lands easier and hurts more; being ganged up on or surrounded
is worse still."""

import random
import unittest

from engine.battle import BattleField, BattleSession, Squad
from engine.battle import battle_ai as ai
from engine.battle import battle_facing as bf_face


class TestArcGeometry(unittest.TestCase):
    def test_arc_relative_to_facing_east(self):
        f = (1, 0)                       # the target looks east
        tgt = (5, 5)
        self.assertEqual(bf_face.arc(f, (6, 5), tgt), "front")   # E
        self.assertEqual(bf_face.arc(f, (6, 4), tgt), "front")   # NE
        self.assertEqual(bf_face.arc(f, (5, 4), tgt), "flank")   # N
        self.assertEqual(bf_face.arc(f, (5, 6), tgt), "flank")   # S
        self.assertEqual(bf_face.arc(f, (4, 5), tgt), "rear")    # W
        self.assertEqual(bf_face.arc(f, (4, 4), tgt), "rear")    # NW

    def test_face_toward(self):
        self.assertEqual(bf_face.face_toward(0, 0, 5, 0), (1, 0))
        self.assertEqual(bf_face.face_toward(5, 5, 5, 0), (0, -1))
        self.assertEqual(bf_face.face_toward(5, 5, 5, 5), (1, 0))  # default


class TestPositionMods(unittest.TestCase):
    def _lone(self):
        bf = BattleField(12, 12)
        tgt = Squad.raise_squad("t", "blue", "infantry_sword", [(6, 6)])
        atk = Squad.raise_squad("a", "red", "infantry_sword", [(7, 6)])
        bf.add_squad(tgt)
        bf.add_squad(atk)
        return bf, atk.soldiers[0], tgt.soldiers[0]

    def test_arc_bonuses_escalate(self):
        bf, a, t = self._lone()          # attacker sits due east
        t.facing = (1, 0)                # east = front
        self.assertEqual(ai._position_mods(bf, a, t), (0, 1.0))
        t.facing = (0, -1)               # east is now a flank
        self.assertEqual(ai._position_mods(bf, a, t), (2, 1.25))
        t.facing = (-1, 0)               # east is now the rear
        self.assertEqual(ai._position_mods(bf, a, t), (4, 1.5))

    def test_ganged_up_adds_a_bonus(self):
        bf = BattleField(12, 12)
        tgt = Squad.raise_squad("t", "blue", "infantry_sword", [(6, 6)])
        atk = Squad.raise_squad("a", "red", "infantry_sword",
                                [(7, 6), (5, 6)])   # both sides
        bf.add_squad(tgt)
        bf.add_squad(atk)
        t = tgt.soldiers[0]
        t.facing = (1, 0)
        th, dm = ai._position_mods(bf, atk.soldiers[0], t)
        self.assertGreaterEqual(th, 2)   # +2 for ≥2 adjacent
        self.assertGreater(dm, 1.0)

    def test_adjacent_enemies_and_surround(self):
        bf = BattleField(12, 12)
        tgt = Squad.raise_squad("t", "blue", "infantry_sword", [(6, 6)])
        ring = [(5, 6), (7, 6), (6, 5), (6, 7)]
        atk = Squad.raise_squad("a", "red", "infantry_sword", ring)
        bf.add_squad(tgt)
        bf.add_squad(atk)
        t = tgt.soldiers[0]
        self.assertEqual(ai.adjacent_enemies(bf, t), 4)
        self.assertTrue(ai.is_surrounded(bf, t))


class TestFlankingInPractice(unittest.TestCase):
    def test_rear_attacks_are_deadlier(self):
        def avg_dmg(target_faces, rolls=1500):
            total = 0
            for seed in range(rolls):
                bf = BattleField(12, 12)
                a = Squad.raise_squad("a", "red", "infantry_sword",
                                      [(7, 6)])
                t = Squad.raise_squad("t", "blue", "infantry_sword",
                                      [(6, 6)])
                bf.add_squad(a)
                bf.add_squad(t)
                t.soldiers[0].facing = target_faces
                before = t.soldiers[0].hp
                ai.attack(bf, a.soldiers[0], a, t.soldiers[0],
                          random.Random(seed))
                total += before - t.soldiers[0].hp
            return total / rolls
        front = avg_dmg((1, 0))          # facing the attacker
        rear = avg_dmg((-1, 0))          # back to the attacker
        self.assertGreater(rear, front * 1.3, "a hit in the back bites")

    def test_facing_updates_as_a_soldier_moves(self):
        bf = BattleField(20, 6)
        mover = Squad.raise_squad("m", "red", "infantry_sword", [(2, 3)])
        foe = Squad.raise_squad("f", "blue", "infantry_sword", [(18, 3)])
        mover.set_order("charge", "f")
        foe.set_order("hold")
        bf.add_squad(mover)
        bf.add_squad(foe)
        sess = BattleSession(bf, seed=1)
        for _ in range(3):
            sess.tick()
        self.assertEqual(mover.soldiers[0].facing, (1, 0),
                         "advancing east, he faces east")

    def test_facing_round_trips(self):
        s = Squad.raise_squad("s", "red", "infantry_sword", [(1, 1)])
        s.soldiers[0].facing = (-1, 1)
        from engine.battle.battle_unit import Squad as SQ
        r = SQ.from_dict(s.to_dict())
        self.assertEqual(r.soldiers[0].facing, (-1, 1))


if __name__ == "__main__":
    unittest.main()
