"""T1.2 — level-up perks (build agency)."""

import unittest

from engine import perks


class _Char:
    def __init__(self, cls="warrior"):
        self.character_class = type("K", (), {"value": cls})()
        self.name = "Hero"
        self.level = 1
        self.metadata = {}
        self.max_hp = 20
        self.hp = 20
        self.strength = self.dexterity = self.constitution = 12
        self.intelligence = self.wisdom = self.charisma = 10


class TestPerks(unittest.TestCase):
    def test_award_and_spend_a_point(self):
        c = _Char()
        perks.award_perk_point(c)
        self.assertEqual(perks.perk_points(c), 1)
        self.assertTrue(perks.grant_perk(c, "toughness"))
        self.assertEqual(perks.perk_points(c), 0)
        self.assertIn("toughness", perks.owned(c))

    def test_max_hp_perk_bumps_the_pool(self):
        c = _Char()
        perks.grant_perk(c, "toughness")           # +8 max_hp
        self.assertEqual(c.max_hp, 28)

    def test_bonuses_aggregate(self):
        c = _Char()
        perks.grant_perk(c, "brawler")             # +1 damage
        perks.grant_perk(c, "mighty")              # +1 strength
        b = perks.perk_bonuses(c)
        self.assertEqual(b.get("damage"), 1)
        self.assertEqual(b.get("strength"), 1)

    def test_class_gated_perks(self):
        warrior, wizard = _Char("warrior"), _Char("wizard")
        self.assertIn("berserker", perks.available_perks(warrior))
        self.assertNotIn("berserker", perks.available_perks(wizard))
        self.assertIn("battlemage", perks.available_perks(wizard))
        self.assertNotIn("battlemage", perks.available_perks(warrior))

    def test_cant_take_a_perk_twice(self):
        c = _Char()
        perks.grant_perk(c, "toughness")
        self.assertNotIn("toughness", perks.available_perks(c))
        self.assertFalse(perks.grant_perk(c, "toughness"))

    def test_perk_bonus_reaches_effects(self):
        # the integration: a perk's bonus folds into engine.effects
        from engine import effects
        c = _Char()
        base_ac = effects.effective_ac(c)
        perks.grant_perk(c, "ironhide")            # +1 armor (AC)
        self.assertEqual(effects.effective_ac(c), base_ac + 1)

    def test_levelup_awards_a_perk_point(self):
        from engine.leveling import check_level_up, xp_threshold
        c = _Char()
        c.level = 1
        c.metadata = {"xp": xp_threshold(2)}       # enough for one level-up
        check_level_up(c)
        self.assertGreaterEqual(perks.perk_points(c), 1,
                                "a level-up grants a perk point")


if __name__ == "__main__":
    unittest.main()
