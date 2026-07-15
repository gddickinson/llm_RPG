"""Armour, shields & damage types (P17.10): armour turns some damage
types and not others, a shield guards the front (best vs arrows), and
weight is a (data-defined) tax — so heavy cavalry ride out an arrow-storm."""

import unittest

from engine.battle import BattleField, Squad
from engine.battle import battle_ai as ai
from engine.battle import battle_armour as armour


class _Max:
    def randint(self, a, b):
        return b

    def random(self):
        return 0.0


class _Fixed:
    def __init__(self, v):
        self.v = v

    def randint(self, a, b):
        return self.v

    def random(self):
        return 0.0


class TestResistTable(unittest.TestCase):
    def test_mail_shrugs_slash_but_pierce_punches_through(self):
        self.assertLess(armour.resist_mult("mail", "slash"), 1.0)
        self.assertGreater(armour.resist_mult("mail", "pierce"), 1.0)

    def test_plate_turns_blade_and_point_but_not_the_mace(self):
        self.assertLess(armour.resist_mult("plate", "slash"), 1.0)
        self.assertLess(armour.resist_mult("plate", "pierce"), 1.0)
        self.assertGreater(armour.resist_mult("plate", "blunt"), 1.0)

    def test_unknown_is_neutral(self):
        self.assertEqual(armour.resist_mult("nonsense", "slash"), 1.0)
        self.assertEqual(armour.resist_mult("mail", "acid"), 1.0)

    def test_apply_resist_untyped_passes_through(self):
        self.assertEqual(armour.apply_resist(10, None, "slash"), 10)
        self.assertEqual(armour.apply_resist(10, "mail", None), 10)
        self.assertGreaterEqual(armour.apply_resist(10, "plate", "slash"), 1)


class TestShield(unittest.TestCase):
    def test_shield_guards_the_front_only(self):
        st = {"shield": True}
        self.assertGreater(armour.shield_dc_bonus(st, "front", False), 0)
        self.assertEqual(armour.shield_dc_bonus(st, "flank", False), 0)
        self.assertEqual(armour.shield_dc_bonus(st, "rear", False), 0)

    def test_shield_is_worth_more_against_arrows(self):
        st = {"shield": True}
        self.assertGreater(armour.shield_dc_bonus(st, "front", True),
                           armour.shield_dc_bonus(st, "front", False))

    def test_no_shield_no_bonus(self):
        self.assertEqual(armour.shield_dc_bonus({}, "front", True), 0)


class TestWeight(unittest.TestCase):
    def test_plate_weighs_more_than_leather(self):
        self.assertGreater(armour.weight_of({"armour_type": "plate"}),
                           armour.weight_of({"armour_type": "leather"}))

    def test_a_shield_adds_weight(self):
        self.assertGreater(armour.weight_of({"armour_type": "mail",
                                             "shield": True}),
                           armour.weight_of({"armour_type": "mail"}))

    def test_the_unarmoured_carry_nothing(self):
        self.assertEqual(armour.weight_of({}), 0.0)
        self.assertEqual(armour.speed_penalty({}), 0.0)


class TestInBattle(unittest.TestCase):
    def _shot(self, target_archetype, attacker="archer_longbow"):
        """Return damage a single arrow does to one target soldier."""
        bf = BattleField(14, 6)
        arch = Squad.raise_squad("a", "red", attacker, [(3, 3)])
        tgt = Squad.raise_squad("t", "blue", target_archetype, [(7, 3)])
        # face the target AWAY from the archer so its shield doesn't apply
        tgt.soldiers[0].facing = (-1, 0)
        bf.add_squad(arch)
        bf.add_squad(tgt)
        hp0 = tgt.soldiers[0].hp
        ai.attack(bf, arch.soldiers[0], arch, tgt.soldiers[0], _Max())
        return hp0 - tgt.soldiers[0].hp

    def test_heavy_cavalry_ride_out_the_arrow_storm(self):
        # arrows (pierce) barely scratch plate but shred a leather-clad
        # light horseman
        plate = self._shot("cavalry_heavy")
        leather = self._shot("cavalry_light")
        self.assertLess(plate, leather,
                        "plate turns the arrow the leather rider takes")

    def test_a_shield_blunts_a_frontal_shot(self):
        bf = BattleField(14, 6)
        arch = Squad.raise_squad("a", "red", "archer_longbow", [(3, 3)])
        # infantry_sword carries a shield; face it AT the archer (front)
        tgt = Squad.raise_squad("t", "blue", "infantry_sword", [(7, 3)])
        tgt.soldiers[0].facing = (-1, 0)     # toward the archer to the west
        bf.add_squad(arch)
        bf.add_squad(tgt)
        # a marginal roll that the shield's front-arc bonus turns aside
        hp0 = tgt.soldiers[0].hp
        ai.attack(bf, arch.soldiers[0], arch, tgt.soldiers[0], _Fixed(7))
        front_hp = tgt.soldiers[0].hp
        # same roll from behind (no shield) gets through
        tgt.soldiers[0].hp = hp0
        tgt.soldiers[0].facing = (1, 0)      # back to the archer
        landed = ai.attack(bf, arch.soldiers[0], arch,
                           tgt.soldiers[0], _Fixed(7))
        self.assertEqual(front_hp, hp0, "the shield caught the shaft")
        self.assertLess(tgt.soldiers[0].hp, hp0,
                        "from behind, the same shot lands")


if __name__ == "__main__":
    unittest.main()
