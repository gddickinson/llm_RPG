"""Tests for status effects."""

import unittest

from characters.character import Character
from characters.character_types import CharacterClass, CharacterRace
from characters.status_effects import (
    apply_effect, has_effect, remove_effect, list_effects,
    tick_effects, can_act, attack_damage_modifier,
)


def _new_char():
    return Character(
        id="t", name="Tester",
        character_class=CharacterClass.WARRIOR, race=CharacterRace.HUMAN,
        level=1, strength=12, dexterity=12, constitution=12,
        intelligence=10, wisdom=10, charisma=10,
        hp=20, max_hp=20,
    )


class TestStatusEffects(unittest.TestCase):
    def test_apply_and_has(self):
        c = _new_char()
        apply_effect(c, "poisoned", 3)
        self.assertTrue(has_effect(c, "poisoned"))
        self.assertEqual(len(list_effects(c)), 1)

    def test_refresh_uses_higher_duration(self):
        c = _new_char()
        apply_effect(c, "blessed", 2)
        apply_effect(c, "blessed", 5)
        self.assertEqual(len(list_effects(c)), 1)
        self.assertEqual(list_effects(c)[0]["duration"], 5)

    def test_unknown_effect_ignored(self):
        c = _new_char()
        apply_effect(c, "fake_effect", 5)
        self.assertEqual(list_effects(c), [])

    def test_remove(self):
        c = _new_char()
        apply_effect(c, "cursed", 5)
        remove_effect(c, "cursed")
        self.assertFalse(has_effect(c, "cursed"))

    def test_can_act_paralyzed(self):
        c = _new_char()
        apply_effect(c, "paralyzed", 2)
        self.assertFalse(can_act(c))

    def test_can_act_default(self):
        c = _new_char()
        self.assertTrue(can_act(c))

    def test_blessed_damage_mod(self):
        c = _new_char()
        apply_effect(c, "blessed", 5)
        self.assertEqual(attack_damage_modifier(c), 1)

    def test_cursed_damage_mod(self):
        c = _new_char()
        apply_effect(c, "cursed", 5)
        self.assertEqual(attack_damage_modifier(c), -1)

    def test_poison_ticks_damage(self):
        c = _new_char()
        before = c.hp
        apply_effect(c, "poisoned", 2)
        events = tick_effects(c)
        self.assertEqual(c.hp, before - 1)
        self.assertTrue(any("poison" in e.lower() for e in events))

    def test_duration_expires(self):
        c = _new_char()
        apply_effect(c, "blessed", 1)
        tick_effects(c)
        self.assertFalse(has_effect(c, "blessed"))


if __name__ == "__main__":
    unittest.main()
