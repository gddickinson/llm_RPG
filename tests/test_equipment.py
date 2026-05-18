"""Tests for the equipment-slots system."""

import unittest

from characters.character import Character
from characters.character_types import CharacterClass, CharacterRace
from characters.equipment import (
    EquipSlot, equip, unequip, get_equipment,
    equipped_weapon, total_armor, weapon_damage,
    slot_for_item, to_dict, from_dict,
)
from items.item_registry import create_item


def _new_char():
    return Character(
        id="t", name="Tester",
        character_class=CharacterClass.WARRIOR, race=CharacterRace.HUMAN,
        level=1, strength=12, dexterity=12, constitution=12,
        intelligence=10, wisdom=10, charisma=10,
        hp=20, max_hp=20,
    )


class TestEquipment(unittest.TestCase):
    def test_default_empty(self):
        c = _new_char()
        eq = get_equipment(c)
        for slot in EquipSlot:
            self.assertIsNone(eq[slot.value])

    def test_equip_weapon(self):
        c = _new_char()
        sword = create_item("sword")
        c.inventory.append(sword)
        msg = equip(c, sword)
        self.assertIn("equip", msg.lower())
        self.assertEqual(equipped_weapon(c).id, "sword")
        self.assertNotIn(sword, c.inventory)

    def test_equip_replaces(self):
        c = _new_char()
        sword = create_item("sword")
        longsword = create_item("longsword")
        c.inventory.append(sword)
        c.inventory.append(longsword)
        equip(c, sword)
        msg = equip(c, longsword)
        self.assertIn("replacing", msg.lower())
        self.assertEqual(equipped_weapon(c).id, "longsword")
        # Old sword is back in inventory
        self.assertIn(sword, c.inventory)

    def test_armor_and_shield(self):
        c = _new_char()
        leather = create_item("leather")
        shield = create_item("shield")
        c.inventory.extend([leather, shield])
        equip(c, leather)
        equip(c, shield)
        self.assertEqual(total_armor(c), 4)  # 2 + 2

    def test_unequip(self):
        c = _new_char()
        sword = create_item("sword")
        c.inventory.append(sword)
        equip(c, sword)
        msg = unequip(c, EquipSlot.WEAPON)
        self.assertIn("unequip", msg.lower())
        self.assertIsNone(equipped_weapon(c))
        self.assertIn(sword, c.inventory)

    def test_cannot_equip_consumable(self):
        c = _new_char()
        potion = create_item("potion")
        c.inventory.append(potion)
        self.assertIsNone(slot_for_item(potion))
        msg = equip(c, potion)
        self.assertIn("can't", msg.lower())

    def test_roundtrip(self):
        c = _new_char()
        sword = create_item("sword")
        c.inventory.append(sword)
        equip(c, sword)
        d = to_dict(c)
        c2 = _new_char()
        from_dict(c2, d)
        self.assertEqual(equipped_weapon(c2).id, "sword")


if __name__ == "__main__":
    unittest.main()
