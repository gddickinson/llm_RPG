"""Data-driven content validation (P1).

Loads every data file and checks cross-references: any item id mentioned
by recipes, loot tables, shop catalogs, dungeon loot, forage tables, or
quest rewards must exist in the item registry.
"""

import unittest

from items.data_loader import load_data_dir, DataError
from items.item_registry import ITEM_REGISTRY, create_item
from items.item import Item, ItemType


class TestItemData(unittest.TestCase):
    def test_registry_loads_from_json(self):
        self.assertGreaterEqual(len(ITEM_REGISTRY), 60)
        for item_id, item in ITEM_REGISTRY.items():
            self.assertIsInstance(item, Item)
            self.assertEqual(item.id, item_id)
            self.assertTrue(item.name)

    def test_create_item_returns_fresh_copies(self):
        a = create_item("potion")
        b = create_item("potion")
        self.assertIsNot(a, b)
        self.assertEqual(a.name, b.name)

    def test_key_items_present_with_correct_stats(self):
        """Spot-check migrated values against the old Python registry."""
        sword = ITEM_REGISTRY["sword"]
        self.assertEqual((sword.damage, sword.value), (6, 30))
        self.assertEqual(sword.item_type, ItemType.WEAPON)
        potion = ITEM_REGISTRY["potion"]
        self.assertEqual(potion.heal_amount, 15)
        self.assertTrue(potion.stackable)
        staff = ITEM_REGISTRY["staff"]
        self.assertEqual(staff.equip_bonuses.get("max_mana"), 3)
        arrow = ITEM_REGISTRY["arrow"]
        self.assertEqual(arrow.ammo_type, "arrow")
        scroll = ITEM_REGISTRY["scroll_fireball"]
        self.assertEqual(scroll.use_effect.get("spell"), "fireball")

    def test_duplicate_ids_rejected(self):
        import os
        import tempfile
        import json
        with tempfile.TemporaryDirectory() as tmp:
            sub = os.path.join(tmp, "things")
            os.makedirs(sub)
            for fname in ("a.json", "b.json"):
                with open(os.path.join(sub, fname), "w") as fp:
                    json.dump({"dup": {"id": "dup", "name": "Dup"}}, fp)
            with self.assertRaises(DataError):
                load_data_dir("things", root=tmp)


class TestCrossReferences(unittest.TestCase):
    def assert_ids_exist(self, ids, source):
        missing = [i for i in ids if i not in ITEM_REGISTRY]
        self.assertFalse(missing, f"{source} references unknown items: "
                                  f"{missing}")

    def test_recipes_reference_real_items(self):
        from items.crafting import RECIPES
        for rid, recipe in RECIPES.items():
            self.assert_ids_exist([recipe.output_id], f"recipe {rid}")
            self.assert_ids_exist(recipe.ingredients.keys(),
                                  f"recipe {rid} ingredients")

    def test_loot_tables_reference_real_items(self):
        from items import loot_tables
        for name in dir(loot_tables):
            table = getattr(loot_tables, name)
            if isinstance(table, dict):
                for key, entries in table.items():
                    if not isinstance(entries, (list, tuple)):
                        continue
                    for entry in entries:
                        if isinstance(entry, (list, tuple)) and entry and \
                                isinstance(entry[0], str):
                            if entry[0] in ITEM_REGISTRY:
                                continue
                            # Only flag strings that look like item ids
                            self.assertIn(
                                entry[0], ITEM_REGISTRY,
                                f"loot table {name}[{key}] references "
                                f"unknown item '{entry[0]}'")

    def test_shop_catalogs_reference_real_items(self):
        from engine.shop import SHOP_CATALOGS
        for cat, ids in SHOP_CATALOGS.items():
            self.assert_ids_exist(ids, f"shop catalog '{cat}'")

    def test_forage_tables_reference_real_items(self):
        from world.foraging import TERRAIN_FORAGE_TABLE
        for terrain, table in TERRAIN_FORAGE_TABLE.items():
            self.assert_ids_exist([iid for iid, _ in table],
                                  f"forage table {terrain}")

    def test_dungeon_loot_references_real_items(self):
        ids = ["potion", "coins", "bandage", "old_map", "rusty_key",
               "herb_bundle"]
        self.assert_ids_exist(ids, "dungeon loot list")

    def test_quest_rewards_reference_real_items(self):
        from quests.quest_templates import QUEST_TEMPLATES
        for qid, factory in QUEST_TEMPLATES.items():
            quest = factory()
            self.assert_ids_exist(quest.reward_items,
                                  f"quest {qid} rewards")


if __name__ == "__main__":
    unittest.main()
