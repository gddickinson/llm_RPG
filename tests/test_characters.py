"""
Smoke tests for character creation and basic operations in LLM-RPG v1.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from characters.character import Character
from characters.character_types import CharacterClass, CharacterRace, Alignment


class TestCharacterTypes:
    def test_character_class_values(self):
        assert CharacterClass.WARRIOR.value == "warrior"
        assert CharacterClass.WIZARD.value == "wizard"

    def test_character_race_values(self):
        assert CharacterRace.HUMAN.value == "human"
        assert CharacterRace.ELF.value == "elf"

    def test_alignment_values(self):
        assert Alignment.LAWFUL_GOOD.value == "lawful good"
        assert Alignment.CHAOTIC_EVIL.value == "chaotic evil"


class TestCharacter:
    def _make_character(self, **overrides):
        defaults = dict(
            id="test-1",
            name="Test Hero",
            character_class=CharacterClass.WARRIOR,
            race=CharacterRace.HUMAN,
            level=1,
            strength=14,
            dexterity=12,
            constitution=13,
            intelligence=10,
            wisdom=10,
            charisma=10,
            hp=20,
            max_hp=20,
        )
        defaults.update(overrides)
        return Character(**defaults)

    def test_create_character(self):
        c = self._make_character()
        assert c.name == "Test Hero"
        assert c.character_class == CharacterClass.WARRIOR
        assert c.hp == 20

    def test_add_memory(self):
        c = self._make_character()
        c.add_memory("Met a stranger", importance=2)
        assert len(c.memories) == 1
        assert c.memories[0]["event"] == "Met a stranger"
        assert c.memories[0]["importance"] == 2

    def test_inventory_starts_empty(self):
        c = self._make_character()
        assert c.inventory == []
        assert c.gold == 0

    def test_default_status(self):
        c = self._make_character()
        assert c.status == "alive"

    def test_position_default(self):
        c = self._make_character()
        assert c.position == (0, 0)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
