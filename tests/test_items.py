"""Tests for the items system."""

import unittest

from items import (
    Item, ItemType, ItemRarity,
    ITEM_REGISTRY, create_item, generate_loot,
)
from items.item_registry import item_by_name


class TestItem(unittest.TestCase):
    def test_basic_item(self):
        item = Item(id="x", name="X", item_type=ItemType.WEAPON,
                    damage=5, value=20)
        self.assertEqual(item.damage, 5)
        self.assertTrue(item.is_weapon())
        self.assertFalse(item.is_armor())
        self.assertFalse(item.is_consumable())

    def test_roundtrip(self):
        item = Item(id="x", name="X", item_type=ItemType.WEAPON,
                    damage=5, value=20, metadata={"foo": "bar"})
        d = item.to_dict()
        item2 = Item.from_dict(d)
        self.assertEqual(item.damage, item2.damage)
        self.assertEqual(item.metadata["foo"], item2.metadata["foo"])
        self.assertEqual(item.item_type, item2.item_type)

    def test_str(self):
        item = create_item("potion", quantity=3)
        self.assertIn("Healing Potion", str(item))
        self.assertIn("x3", str(item))


class TestRegistry(unittest.TestCase):
    def test_known_ids(self):
        for key in ("sword", "potion", "shield", "longsword",
                    "leather", "crude_axe"):
            item = create_item(key)
            self.assertIsNotNone(item, f"{key} should exist")
            self.assertEqual(item.id, key)

    def test_unknown(self):
        self.assertIsNone(create_item("nonsense_item"))

    def test_quantity(self):
        item = create_item("potion", quantity=5)
        self.assertEqual(item.quantity, 5)

    def test_by_name(self):
        item = item_by_name("sword")
        self.assertIsNotNone(item)
        # Substring match — should find one of the swords
        self.assertIn("Sword", item.name)


class TestLoot(unittest.TestCase):
    def test_loot_for_brigand(self):
        import random

        class C:
            level = 3

            class character_class:
                value = "brigand"
        drops = generate_loot(C(), rng=random.Random(1))
        self.assertTrue(drops)
        for it in drops:
            self.assertIsInstance(it, Item)

    def test_loot_unknown_class(self):
        import random

        class C:
            level = 1

            class character_class:
                value = "nonsense"
        drops = generate_loot(C(), rng=random.Random(1))
        # Falls back to default table
        self.assertTrue(drops)


if __name__ == "__main__":
    unittest.main()
