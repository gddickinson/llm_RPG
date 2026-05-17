"""Tests for the skill system."""

import random
import unittest

from engine.skills import (
    Skill, Difficulty,
    ability_modifier, proficiency_bonus,
    roll_check, opposed_check,
)


class TestSkills(unittest.TestCase):
    def test_ability_modifier(self):
        self.assertEqual(ability_modifier(10), 0)
        self.assertEqual(ability_modifier(12), 1)
        self.assertEqual(ability_modifier(8), -1)
        self.assertEqual(ability_modifier(20), 5)

    def test_proficiency_bonus(self):
        self.assertEqual(proficiency_bonus(1), 2)
        self.assertEqual(proficiency_bonus(4), 2)
        self.assertEqual(proficiency_bonus(5), 3)
        self.assertEqual(proficiency_bonus(9), 4)

    def test_roll_with_high_ability(self):
        class C:
            level = 1
            charisma = 20
            name = "X"
        # 20 ability gives +5; with prof bonus +2 => total floor is 8 (1+5+2)
        # DC 10 should usually succeed
        successes = 0
        for _ in range(200):
            ok, _, _ = roll_check(C(), Skill.PERSUASION, dc=10, proficient=True,
                                  rng=random.Random())
            if ok:
                successes += 1
        # Should succeed clearly more than half the time
        self.assertGreater(successes, 130)

    def test_advantage_helps(self):
        class C:
            level = 1
            wisdom = 10
            name = "Y"
        # Run with advantage vs without — advantage should average higher
        adv_total, plain_total = 0, 0
        rng = random.Random(0)
        for _ in range(200):
            _, t1, _ = roll_check(C(), Skill.PERCEPTION, dc=0,
                                  advantage=True, rng=rng)
            _, t2, _ = roll_check(C(), Skill.PERCEPTION, dc=0,
                                  rng=rng)
            adv_total += t1
            plain_total += t2
        self.assertGreater(adv_total, plain_total)

    def test_opposed(self):
        class A:
            level = 1
            charisma = 20
            name = "A"

        class B:
            level = 1
            wisdom = 8
            name = "B"
        wins = sum(opposed_check(A(), Skill.DECEPTION,
                                 B(), Skill.INSIGHT,
                                 rng=random.Random())[0]
                   for _ in range(200))
        # Strong CHA should win majority
        self.assertGreater(wins, 100)


if __name__ == "__main__":
    unittest.main()
