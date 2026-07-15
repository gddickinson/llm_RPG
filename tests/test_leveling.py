"""Tests for the leveling system."""

import unittest

from characters.character import Character
from characters.character_types import CharacterClass, CharacterRace
from engine.leveling import (
    xp_threshold, level_for_xp, xp_to_next,
    award_xp, check_level_up,
)


def _new_char(klass=CharacterClass.WARRIOR, level=1):
    return Character(
        id="t", name="Tester",
        character_class=klass, race=CharacterRace.HUMAN,
        level=level, strength=14, dexterity=12, constitution=13,
        intelligence=10, wisdom=10, charisma=10,
        hp=20, max_hp=20,
    )


class TestThresholds(unittest.TestCase):
    def test_level_one_is_zero(self):
        self.assertEqual(xp_threshold(1), 0)

    def test_increasing(self):
        for n in range(2, 20):
            self.assertGreater(xp_threshold(n + 1), xp_threshold(n))

    def test_level_for_xp(self):
        # P37.5 much steeper curve: L2=300, L3=900, L4=1800
        self.assertEqual(level_for_xp(0), 1)
        self.assertEqual(level_for_xp(299), 1)
        self.assertEqual(level_for_xp(300), 2)
        self.assertEqual(level_for_xp(899), 2)
        self.assertEqual(level_for_xp(900), 3)

    def test_curve_is_a_slow_grind(self):
        # a deliberately slow climb — the first level costs 300 (was 100/120)
        self.assertEqual(xp_threshold(2), 300)
        self.assertEqual(xp_threshold(3), 900)
        self.assertEqual(xp_threshold(4), 1800)

    def test_xp_to_next(self):
        cur, need = xp_to_next(400)              # mid-way through level 2
        self.assertEqual(cur + xp_threshold(2), 400)
        self.assertEqual(need, xp_threshold(3) - xp_threshold(2))


class TestLevelUp(unittest.TestCase):
    def test_no_levelup_below_threshold(self):
        c = _new_char()
        c.metadata = {"xp": 50}
        msgs = check_level_up(c)
        self.assertEqual(msgs, [])
        self.assertEqual(c.level, 1)

    def test_levelup_at_threshold(self):
        c = _new_char()
        c.metadata = {"xp": 300}         # P37.5 L2 threshold
        msgs = check_level_up(c)
        self.assertEqual(len(msgs), 1)
        self.assertEqual(c.level, 2)
        self.assertEqual(c.max_hp, 25)  # +5
        self.assertEqual(c.hp, 25)      # full heal
        # Warrior favors STR + CON
        self.assertEqual(c.strength, 15)
        self.assertEqual(c.constitution, 14)

    def test_multi_level_skip(self):
        c = _new_char()
        c.metadata = {"xp": 1800}  # enough for level 4 (P37.5 curve)
        msgs = check_level_up(c)
        self.assertEqual(len(msgs), 3)
        self.assertEqual(c.level, 4)
        self.assertEqual(c.max_hp, 35)  # +5 x 3

    def test_award_xp(self):
        c = _new_char()
        c.metadata = {"xp": 0}
        msgs = award_xp(c, 300)
        self.assertEqual(c.metadata["xp"], 300)
        self.assertEqual(c.level, 2)
        self.assertEqual(len(msgs), 1)

    def test_class_specific_stats(self):
        c = _new_char(klass=CharacterClass.WIZARD)
        c.intelligence = 10
        c.wisdom = 10
        c.metadata = {"xp": 300}
        check_level_up(c)
        # Wizard favors INT + WIS
        self.assertEqual(c.intelligence, 11)
        self.assertEqual(c.wisdom, 11)


if __name__ == "__main__":
    unittest.main()
