"""Fire & the battle surface layer (P17.E4): flame burns, spreads,
eats cover and gates, and a fire arrow lights the tile it strikes."""

import unittest

from engine.battle import BattleField, Squad
from engine.battle import battle_fire as fire
from engine.battle import battle_ai as ai


class _Zero:                     # every spread roll succeeds
    def randint(self, a, b):
        return b

    def random(self):
        return 0.0


class _NoSpread:                 # every spread roll fails
    def randint(self, a, b):
        return b

    def random(self):
        return 1.0


class TestIgniteAndBurn(unittest.TestCase):
    def test_ignite_makes_fire(self):
        bf = BattleField(10, 8)
        fire.ignite(bf, 4, 4)
        self.assertEqual(bf.surfaces[(4, 4)]["kind"], "fire")

    def test_fire_burns_a_soldier_standing_in_it(self):
        bf = BattleField(10, 8)
        sq = Squad.raise_squad("s", "blue", "infantry_sword", [(4, 4)])
        bf.add_squad(sq)
        hp0 = sq.soldiers[0].hp
        fire.ignite(bf, 4, 4)
        fire.tick(bf, _NoSpread())
        self.assertEqual(sq.soldiers[0].hp, hp0 - fire.FIRE_DAMAGE)

    def test_fire_eats_the_treeline(self):
        bf = BattleField(10, 8)
        bf.terrain[4][4] = "forest"
        fire.ignite(bf, 4, 4)
        fire.tick(bf, _NoSpread())
        self.assertEqual(bf.terrain[4][4], "scorched")   # cover gone

    def test_fire_guts_out_to_scorched(self):
        bf = BattleField(10, 8)
        fire.ignite(bf, 4, 4, duration=1)
        fire.tick(bf, _NoSpread())
        self.assertNotIn((4, 4), bf.surfaces)            # burned out
        self.assertEqual(bf.terrain[4][4], "scorched")


class TestSpread(unittest.TestCase):
    def test_fire_spreads_to_adjacent_forest(self):
        bf = BattleField(10, 8)
        bf.terrain[4][5] = "forest"
        fire.ignite(bf, 4, 4)
        fire.tick(bf, _Zero())                           # forced spread
        self.assertIn((5, 4), bf.surfaces)
        self.assertEqual(bf.surfaces[(5, 4)]["kind"], "fire")

    def test_no_spread_across_bare_ground(self):
        bf = BattleField(10, 8)                          # all grass
        fire.ignite(bf, 4, 4)
        fire.tick(bf, _Zero())
        self.assertNotIn((5, 4), bf.surfaces)            # grass doesn't catch

    def test_an_oil_pool_all_goes_up(self):
        bf = BattleField(12, 8)
        fire.pour_oil(bf, 5, 4, radius=2)
        n_oil = sum(1 for s in bf.surfaces.values() if s["kind"] == "oil")
        fire.ignite(bf, 5, 4)                            # touch one corner
        n_fire = sum(1 for s in bf.surfaces.values() if s["kind"] == "fire")
        self.assertEqual(n_fire, n_oil, "the whole slick catches at once")


class TestStructures(unittest.TestCase):
    def test_fire_breaches_a_timber_gate(self):
        bf = BattleField(10, 8)
        bf.add_wall(4, 4, "gate")
        hp0 = bf.struct_hp[(4, 4)]
        fire.ignite(bf, 4, 4)
        fire.tick(bf, _NoSpread())
        self.assertLess(bf.struct_hp.get((4, 4), 0), hp0)

    def test_stone_does_not_burn(self):
        bf = BattleField(10, 8)
        bf.add_wall(4, 4, "stone_wall")
        hp0 = bf.struct_hp[(4, 4)]
        fire.ignite(bf, 4, 4)
        fire.tick(bf, _NoSpread())
        self.assertEqual(bf.struct_hp[(4, 4)], hp0)      # stone shrugs it off


class TestFireArrowsAndPersistence(unittest.TestCase):
    def test_a_fire_arrow_lights_the_target_tile(self):
        bf = BattleField(16, 8)
        arch = Squad.raise_squad("a", "red", "archer_fire", [(2, 4)])
        tgt = Squad.raise_squad("t", "blue", "infantry_sword", [(6, 4)])
        bf.add_squad(arch)
        bf.add_squad(tgt)
        ai.attack(bf, arch.soldiers[0], arch, tgt.soldiers[0], _Zero())
        self.assertIn((6, 4), bf.surfaces)
        self.assertEqual(bf.surfaces[(6, 4)]["kind"], "fire")

    def test_surfaces_round_trip(self):
        bf = BattleField(10, 8)
        fire.ignite(bf, 3, 3)
        fire.pour_oil(bf, 6, 6, radius=0)
        clone = BattleField.from_dict(bf.to_dict())
        self.assertEqual(clone.surfaces[(3, 3)]["kind"], "fire")
        self.assertEqual(clone.surfaces[(6, 6)]["kind"], "oil")


if __name__ == "__main__":
    unittest.main()
