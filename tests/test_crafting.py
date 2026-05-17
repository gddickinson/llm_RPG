"""Tests for the crafting system."""

import unittest

from items.crafting import (
    can_craft, craft, find_recipe, list_recipes,
)
from items.item_registry import create_item


class FakePlayer:
    def __init__(self, gold=100):
        self.gold = gold
        self.inventory = []


class TestCrafting(unittest.TestCase):
    def test_recipe_lookup(self):
        self.assertIsNotNone(find_recipe("potion"))
        self.assertIsNone(find_recipe("nonsense"))

    def test_recipe_list_nonempty(self):
        self.assertGreater(len(list_recipes()), 0)

    def test_can_craft_no_ingredients(self):
        p = FakePlayer(gold=100)
        err = can_craft(p, "potion")
        # Error mentions the missing ingredient by display name
        self.assertIn("herb", err.lower())

    def test_can_craft_no_gold(self):
        p = FakePlayer(gold=0)
        p.inventory.append(create_item("herb_bundle"))
        err = can_craft(p, "potion")
        # Error includes "g" cost indicator
        self.assertIn("5g", err.lower())

    def test_successful_craft_potion(self):
        p = FakePlayer(gold=100)
        p.inventory.append(create_item("herb_bundle"))
        msg = craft(p, "potion")
        self.assertIn("craft", msg.lower())
        # Player now has a Healing Potion
        names = [getattr(i, "name", "") for i in p.inventory]
        self.assertIn("Healing Potion", names)
        # Herb consumed
        ids = [getattr(i, "id", "") for i in p.inventory]
        self.assertNotIn("herb_bundle", ids)

    def test_forge_required(self):
        p = FakePlayer(gold=100)
        for _ in range(5):
            p.inventory.append(create_item("coins"))
        # No location property -> fail
        err = can_craft(p, "sword", location_properties={})
        self.assertIn("forge", err.lower())
        # With forge -> success
        err = can_craft(p, "sword", location_properties={"forge": True})
        self.assertEqual(err, "")


if __name__ == "__main__":
    unittest.main()
