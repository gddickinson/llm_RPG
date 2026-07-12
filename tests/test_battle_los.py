"""Battle line-of-sight (P17.E3): you can't loose an arrow through a
treeline, a wall, or a ridge — cover conceals as well as protects."""

import unittest

from engine.battle import BattleField, Squad
from engine.battle import battle_ai as ai
from engine.battle import battle_terrain as terrain


class _Max:
    def randint(self, a, b):
        return b


class TestHasLos(unittest.TestCase):
    def test_clear_ground_is_visible(self):
        bf = BattleField(14, 8)
        self.assertTrue(terrain.has_los(bf, (2, 4), (10, 4)))

    def test_a_wall_blocks_the_shot(self):
        bf = BattleField(14, 8)
        bf.terrain[4][6] = "wall"
        self.assertFalse(terrain.has_los(bf, (2, 4), (10, 4)))

    def test_a_treeline_blocks_the_shot(self):
        bf = BattleField(14, 8)
        for x in (5, 6, 7):
            bf.terrain[4][x] = "forest"
        self.assertFalse(terrain.has_los(bf, (2, 4), (10, 4)))

    def test_low_cover_is_seen_over(self):
        bf = BattleField(14, 8)
        bf.terrain[4][6] = "hedge"          # cover, but not sight-blocking
        self.assertTrue(terrain.has_los(bf, (2, 4), (10, 4)))

    def test_the_archer_sees_out_of_its_own_wood(self):
        bf = BattleField(14, 8)
        bf.terrain[4][2] = "forest"          # the shooter stands in it
        self.assertTrue(terrain.has_los(bf, (2, 4), (10, 4)))


class TestRangedThroughCover(unittest.TestCase):
    def _duel(self, wall):
        bf = BattleField(16, 8)
        arch = Squad.raise_squad("a", "red", "archer_longbow", [(2, 4)])
        tgt = Squad.raise_squad("t", "blue", "infantry_sword", [(6, 4)])
        if wall:
            bf.terrain[4][4] = "wall"        # between them
        bf.add_squad(arch)
        bf.add_squad(tgt)
        return bf, arch, tgt

    def test_cannot_shoot_through_a_wall(self):
        bf, arch, tgt = self._duel(wall=True)
        hp0 = tgt.soldiers[0].hp
        ai.attack(bf, arch.soldiers[0], arch, tgt.soldiers[0], _Max())
        self.assertEqual(tgt.soldiers[0].hp, hp0, "the wall stops the arrow")

    def test_a_clear_shot_lands(self):
        bf, arch, tgt = self._duel(wall=False)
        hp0 = tgt.soldiers[0].hp
        ai.attack(bf, arch.soldiers[0], arch, tgt.soldiers[0], _Max())
        self.assertLess(tgt.soldiers[0].hp, hp0, "an open lane hits")

    def test_shoots_from_the_edge_of_a_wood(self):
        bf, arch, tgt = self._duel(wall=False)
        bf.terrain[4][2] = "forest"          # the archer is IN the trees
        hp0 = tgt.soldiers[0].hp
        ai.attack(bf, arch.soldiers[0], arch, tgt.soldiers[0], _Max())
        self.assertLess(tgt.soldiers[0].hp, hp0, "it fires from the edge")


if __name__ == "__main__":
    unittest.main()
