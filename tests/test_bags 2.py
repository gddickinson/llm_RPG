"""P25.2 — magical bags & rucksacks raise carry capacity."""

import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import unittest

from items.item_registry import create_item
from items.item import Item
from engine.carry import (capacity, used_slots, can_carry,
                          bag_bonus, ammo_capacity)


def _hero(strength=10):
    from characters.character import Character
    from characters.character_types import CharacterClass, CharacterRace
    return Character(
        id="h", name="H", character_class=CharacterClass.WARRIOR,
        race=CharacterRace.HUMAN, level=1, strength=strength, dexterity=10,
        constitution=10, intelligence=10, wisdom=10, charisma=10,
        hp=20, max_hp=20)


class TestBagItems(unittest.TestCase):
    def test_bag_items_exist_with_their_bonus(self):
        for bid, key, val in (("rucksack", "carry_bonus", 8),
                              ("explorers_pack", "carry_bonus", 14),
                              ("bottomless_bag", "carry_bonus", 40),
                              ("quiver", "ammo_capacity", 3)):
            it = create_item(bid)
            self.assertIsNotNone(it, f"{bid} should be a registry item")
            self.assertEqual(it.metadata.get(key), val)

    def test_bonus_survives_serialisation(self):
        back = Item.from_dict(create_item("bottomless_bag").to_dict())
        self.assertEqual(back.metadata.get("carry_bonus"), 40)


class TestCarryBonus(unittest.TestCase):
    def test_rucksack_raises_capacity(self):
        h = _hero()
        base = capacity(h)
        h.add_item(create_item("rucksack"))
        self.assertEqual(bag_bonus(h), 8)
        self.assertEqual(capacity(h), base + 8)

    def test_bags_stack_their_bonuses(self):
        h = _hero()
        base = capacity(h)
        h.add_item(create_item("rucksack"))
        h.add_item(create_item("explorers_pack"))
        self.assertEqual(capacity(h), base + 22)

    def test_bottomless_bag_is_a_big_upgrade(self):
        h = _hero()
        base = capacity(h)
        h.add_item(create_item("bottomless_bag"))
        self.assertEqual(capacity(h), base + 40)

    def test_capacity_survives_a_reload(self):
        h = _hero()
        h.add_item(create_item("rucksack"))
        raised = capacity(h)
        # rebuild the inventory the way save/load does
        h.inventory = [Item.from_dict(it.to_dict()) for it in h.inventory]
        self.assertEqual(capacity(h), raised)


class TestQuiver(unittest.TestCase):
    def test_quiver_frees_ammo_slots(self):
        h = _hero()
        h.add_item(create_item("arrow", quantity=40))
        h.add_item(create_item("bolt", quantity=20))
        self.assertEqual(used_slots(h), 2)
        h.add_item(create_item("quiver"))
        # quiver adds a slot but holds both ammo stacks off the pack → net 1
        self.assertEqual(ammo_capacity(h), 3)
        self.assertEqual(used_slots(h), 1)

    def test_quiver_relief_is_capped(self):
        h = _hero()
        # one quiver holds 3 ammo stacks; a 4th still counts
        for a in ("arrow", "bolt", "stone"):
            h.add_item(create_item(a, quantity=5))
        extra = create_item("arrow", quantity=1)
        extra.id = "arrow_special"        # distinct so it doesn't merge
        extra.use_effect = {"flame": True}
        h.add_item(extra)
        h.add_item(create_item("quiver"))
        # 4 ammo stacks + quiver = 5 items; quiver frees 3 → used 2
        self.assertEqual(used_slots(h), 2)

    def test_quiver_lets_a_full_pack_still_hold_ammo(self):
        h = _hero(strength=6)              # small pack
        h.add_item(create_item("quiver"))  # the quiver takes its own slot first
        # fill the REST of the pack to capacity with distinct junk
        i = 0
        while can_carry(h):
            sw = create_item("sword")
            sw.id = f"junk_{i}"
            h.add_item(sw)
            i += 1
        self.assertFalse(can_carry(h))
        # ammo still fits — it rides the quiver, not the general pack
        h.add_item(create_item("arrow", quantity=30))
        self.assertLessEqual(used_slots(h), capacity(h),
                             "ammo on the quiver shouldn't overflow the pack")


class TestBagsAreSold(unittest.TestCase):
    def test_bags_stocked_by_fitting_merchants(self):
        from engine.shop import SHOP_CATALOGS
        self.assertIn("rucksack", SHOP_CATALOGS["general"])
        self.assertIn("quiver", SHOP_CATALOGS["ranger"])
        self.assertIn("bottomless_bag", SHOP_CATALOGS["wizard"])


if __name__ == "__main__":
    unittest.main()
