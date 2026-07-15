"""AI seeks cover (P17.6e, deferred from P17.6a): a foot archer caught in
the open ducks into the nearest cover that still lets it shoot, rather
than trading arrows in the clear."""

import unittest

from engine.battle import BattleField, Squad, BattleSession
from engine.battle import battle_ai as ai


def _sq(archetype, cells, team="red", sid="s"):
    return Squad.raise_squad(sid, team, archetype, cells)


class TestCoverStep(unittest.TestCase):
    def _setup(self, arch_at, cover_at, foe_at, archetype="archer_longbow"):
        bf = BattleField(20, 10)
        if cover_at is not None:
            bf.set_terrain(cover_at[0], cover_at[1], "forest")
        arch = _sq(archetype, [arch_at], team="red", sid="a")
        foe = _sq("infantry_sword", [foe_at], team="blue", sid="f")
        bf.add_squad(arch)
        bf.add_squad(foe)
        return bf, arch, foe

    def test_archer_in_the_open_finds_the_treeline(self):
        bf, arch, foe = self._setup((5, 5), (6, 5), (9, 5))
        step = ai.cover_seek_step(bf, arch.soldiers[0], arch,
                                  foe.soldiers[0])
        self.assertEqual(step, (6, 5), "steps into the wood")

    def test_no_step_when_already_in_the_best_cover(self):
        bf, arch, foe = self._setup((6, 5), (6, 5), (9, 5))
        # the archer is standing ON the forest tile already
        step = ai.cover_seek_step(bf, arch.soldiers[0], arch,
                                  foe.soldiers[0])
        self.assertIsNone(step, "holds — nowhere better")

    def test_no_step_when_cover_is_out_of_range(self):
        # cover far behind the archer, target at the edge of reach
        bf = BattleField(30, 10)
        bf.set_terrain(2, 5, "forest")
        arch = _sq("archer_longbow", [(9, 5)], team="red", sid="a")
        far = 9 + ai.ranged_reach(arch)          # target at max range
        foe = _sq("infantry_sword", [(far, 5)], team="blue", sid="f")
        bf.add_squad(arch)
        bf.add_squad(foe)
        step = ai.cover_seek_step(bf, arch.soldiers[0], arch,
                                  foe.soldiers[0])
        self.assertIsNone(step, "won't break range to reach far cover")

    def test_only_foot_archers_seek_cover(self):
        # a mounted archer (cavalry) does not hunker
        bf, arch, foe = self._setup((5, 5), (6, 5), (9, 5),
                                    archetype="cavalry_mounted_archer")
        self.assertIsNone(ai.cover_seek_step(bf, arch.soldiers[0], arch,
                                             foe.soldiers[0]))

    def test_melee_does_not_seek_cover(self):
        bf, arch, foe = self._setup((5, 5), (6, 5), (9, 5),
                                    archetype="infantry_sword")
        self.assertIsNone(ai.cover_seek_step(bf, arch.soldiers[0], arch,
                                             foe.soldiers[0]))


class TestInBattle(unittest.TestCase):
    def test_archer_moves_into_cover_then_holds(self):
        bf = BattleField(20, 10)
        bf.set_terrain(5, 4, "forest")           # cover beside the shot line
        arch = _sq("archer_longbow", [(5, 5)], team="red", sid="a")
        arch.set_order("hold", "f")              # don't advance; just fight
        foe = _sq("infantry_sword", [(9, 5)], team="blue", sid="f")
        foe.set_order("hold", "a")
        bf.add_squad(arch)
        bf.add_squad(foe)
        sess = BattleSession(bf, seed=1)
        sess.tick()
        self.assertEqual(arch.soldiers[0].pos, (5, 4),
                         "the archer ducked into the wood")
        self.assertGreater(bf.cover_at(*arch.soldiers[0].pos), 0.0)
        # from cover it now holds and shoots, not thrashing back out
        sess.tick()
        self.assertEqual(arch.soldiers[0].pos, (5, 4),
                         "and stays put to loose from cover")

    def test_archer_in_cover_still_kills_over_time(self):
        bf = BattleField(20, 10)
        bf.set_terrain(5, 4, "forest")
        arch = _sq("archer_longbow", [(5, 5)], team="red", sid="a")
        arch.set_order("hold", "f")
        foe = _sq("infantry_sword", [(9, 5)], team="blue", sid="f")
        foe.set_order("hold", "a")
        bf.add_squad(arch)
        bf.add_squad(foe)
        sess = BattleSession(bf, seed=2)
        hp0 = foe.soldiers[0].hp
        for _ in range(12):
            sess.tick()
        self.assertLess(foe.soldiers[0].hp, hp0,
                        "hunkering in cover doesn't stop it shooting")


if __name__ == "__main__":
    unittest.main()
