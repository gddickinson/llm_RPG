"""M1 — magic depth: schools, tiers, and the learning routes.

A fresh caster begins with only NOVICE (tier-1) class spells; higher tiers are
earned by levelling (the innate/trained route) or studied from tomes (which
bypass the tier gate). `can_learn` is the single gate (tier-by-level + a spell's
`requires` block).
"""

import unittest

from engine import spells
from engine.spells import (SPELL_REGISTRY, max_tier_for_level, can_learn,
                           learn_new_spells, teach_spell, starting_spells_for,
                           class_spells)
from characters.character import Character
from characters.character_types import CharacterClass, CharacterRace


def _caster(cls=CharacterClass.WIZARD, level=1, intel=14, wis=12):
    return Character(id="c", name="Caster", character_class=cls,
                     race=CharacterRace.HUMAN, level=level, strength=8,
                     dexterity=10, constitution=10, intelligence=intel,
                     wisdom=wis, charisma=10, hp=20, max_hp=20, position=(0, 0),
                     metadata={})


class TestSchema(unittest.TestCase):
    def test_spells_have_school_and_tier(self):
        for s in SPELL_REGISTRY.values():
            self.assertTrue(s.school, f"{s.id} has no school")
            self.assertGreaterEqual(s.tier, 1)
            self.assertLessEqual(s.tier, 5)

    def test_catalogue_grew(self):
        self.assertGreaterEqual(len(SPELL_REGISTRY), 40)

    def test_tier_by_level(self):
        self.assertEqual(max_tier_for_level(1), 1)
        self.assertEqual(max_tier_for_level(3), 2)
        self.assertEqual(max_tier_for_level(5), 3)
        self.assertEqual(max_tier_for_level(12), 5)


class TestStartingSpells(unittest.TestCase):
    def test_start_is_tier_one_only(self):
        for s in starting_spells_for("wizard"):
            self.assertEqual(s.tier, 1)
        self.assertTrue(starting_spells_for("wizard"))

    def test_class_lists_differ(self):
        wiz = {s.id for s in class_spells("wizard")}
        cle = {s.id for s in class_spells("cleric")}
        self.assertIn("fireball", wiz)
        self.assertNotIn("fireball", cle)
        self.assertIn("heal", cle)
        self.assertNotIn("heal", wiz)

    def test_wizard_starts_without_fireball(self):
        w = _caster()
        spells.ensure_mana(w)
        self.assertIn("magic_missile", w.metadata["spells_known"])
        self.assertNotIn("fireball", w.metadata["spells_known"])   # tier 3


class TestCanLearn(unittest.TestCase):
    def test_tier_gate(self):
        w = _caster(level=1)
        ok, why = can_learn(w, "fireball")            # tier 3, needs L5
        self.assertFalse(ok)
        w.level = 5
        self.assertTrue(can_learn(w, "fireball")[0])

    def test_stat_requirement(self):
        w = _caster(level=12, intel=14)
        ok, _ = can_learn(w, "meteor_swarm")          # needs int 16
        self.assertFalse(ok)
        w.intelligence = 16
        self.assertTrue(can_learn(w, "meteor_swarm")[0])

    def test_wisdom_requirement(self):
        c = _caster(CharacterClass.CLERIC, level=5, wis=12)
        ok, _ = can_learn(c, "greater_heal")          # needs wis 14
        self.assertFalse(ok)
        c.wisdom = 14
        self.assertTrue(can_learn(c, "greater_heal")[0])


class TestLearning(unittest.TestCase):
    def test_levelup_grants_new_tiers(self):
        w = _caster(level=1)
        spells.ensure_mana(w)
        self.assertNotIn("fireball", w.metadata["spells_known"])
        w.level = 5
        learnt = learn_new_spells(w)
        self.assertIn("Fireball", learnt)
        self.assertIn("fireball", w.metadata["spells_known"])

    def test_non_caster_learns_nothing(self):
        war = _caster(CharacterClass.WARRIOR, level=10)
        spells.ensure_mana(war)
        self.assertEqual(learn_new_spells(war), [])
        self.assertEqual(war.metadata["spells_known"], [])

    def test_tome_bypasses_tier_gate(self):
        w = _caster(level=1)                          # too low for fireball innately
        spells.ensure_mana(w)
        self.assertFalse(can_learn(w, "fireball")[0])
        ok, _ = teach_spell(w, "fireball", force=True)   # a tome studies ahead
        self.assertTrue(ok)
        self.assertIn("fireball", w.metadata["spells_known"])

    def test_tome_without_force_respects_gate(self):
        w = _caster(level=1)
        spells.ensure_mana(w)
        ok, _ = teach_spell(w, "fireball", force=False)
        self.assertFalse(ok)


class TestLevelUpIntegration(unittest.TestCase):
    def test_check_level_up_teaches_spells(self):
        from engine.leveling import check_level_up, award_xp
        w = _caster(level=1)
        spells.ensure_mana(w)
        # push enough XP to reach ~level 5
        msgs = award_xp(w, 100000)
        self.assertGreaterEqual(w.level, 5)
        self.assertTrue(any("magic" in m.lower() or "Fireball" in m
                            for m in msgs), msgs)
        self.assertIn("fireball", w.metadata["spells_known"])


if __name__ == "__main__":
    unittest.main()
