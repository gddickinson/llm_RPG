"""Siege (P17.6b): siege engines batter walls into breaches that the
assault then pours through — and only siege engines can."""

import unittest

from engine.battle import BattleField, BattleSession, Squad
from engine.battle import battle_ai as ai
from engine.battle.battle_scenario import build_field


def _wall_and_besieger(besieger_type):
    """A single palisade tile at (10,5), a besieging squad just to its
    left, a garrison out of reach behind it."""
    bf = BattleField(20, 11)
    bf.add_wall(10, 5, "wooden_palisade")
    besieger = Squad.raise_squad("s", "red", besieger_type,
                                 [(8, 5), (8, 6)])
    garrison = Squad.raise_squad("g", "blue", "infantry_sword",
                                 [(14, 5), (14, 6)])
    besieger.set_order("charge", "g")
    garrison.set_order("hold")
    bf.add_squad(besieger)
    bf.add_squad(garrison)
    return bf


class TestSiegeData(unittest.TestCase):
    def test_structural_dmg_property(self):
        ram = Squad.raise_squad("s", "red", "siege_ram", [(0, 0)])
        foot = Squad.raise_squad("f", "red", "infantry_sword", [(0, 0)])
        self.assertGreater(ram.structural_dmg, 0)
        self.assertEqual(foot.structural_dmg, 0)

    def test_nearest_struct(self):
        bf = BattleField(20, 10)
        self.assertIsNone(ai.nearest_struct(bf, 5, 5))
        bf.add_wall(12, 5, "stone_wall")
        bf.add_wall(3, 3, "stone_wall")
        self.assertEqual(ai.nearest_struct(bf, 5, 5), (3, 3))


class TestSiegeBattering(unittest.TestCase):
    def test_a_ram_batters_the_wall(self):
        bf = _wall_and_besieger("siege_ram")
        hp0 = bf.struct_hp[(10, 5)]
        sess = BattleSession(bf, seed=1)
        # a few ticks: the ram closes and then hammers the wall
        for _ in range(6):
            sess.tick()
        self.assertLess(bf.struct_hp.get((10, 5), 0), hp0,
                        "the ram should have battered the palisade")

    def test_infantry_cannot_breach(self):
        bf = _wall_and_besieger("infantry_sword")
        sess = BattleSession(bf, seed=1)
        for _ in range(20):
            sess.tick()
        self.assertEqual(bf.struct_hp.get((10, 5)), 200,
                         "foot soldiers can't batter a wall down")

    def test_siege_opens_a_breach_and_wins(self):
        bf = build_field("siege_assault")
        walls0 = len(bf.struct_hp)
        r = BattleSession(bf, seed=1).run_headless(max_ticks=250)
        self.assertLess(len(bf.struct_hp), walls0,
                        "the rams breached the wall")
        self.assertEqual(r["winner"], "red",
                         "the assault poured through the breach")

    def test_breach_becomes_passable_rubble(self):
        bf = _wall_and_besieger("siege_trebuchet")   # 50/hit, quick
        sess = BattleSession(bf, seed=1)
        for _ in range(30):
            sess.tick()
            if (10, 5) not in bf.struct_hp:
                break
        self.assertNotIn((10, 5), bf.struct_hp, "the wall fell")
        self.assertTrue(bf.passable(10, 5) or
                        bf.soldier_at(10, 5) is not None,
                        "the breach is a lane now (rubble)")


if __name__ == "__main__":
    unittest.main()
