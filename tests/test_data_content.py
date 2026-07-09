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


class TestRecipeSpellShopData(unittest.TestCase):
    def test_recipes_load_from_json(self):
        from items.crafting import RECIPES
        self.assertGreaterEqual(len(RECIPES), 6)
        silver = RECIPES["silver_blade"]
        self.assertEqual(silver.gold_cost, 100)
        self.assertEqual(silver.required_property, "forge")
        self.assertEqual(silver.ingredients.get("troll_tooth"), 1)

    def test_spells_load_from_json(self):
        from engine.spells import SPELL_REGISTRY
        self.assertGreaterEqual(len(SPELL_REGISTRY), 7)
        fireball = SPELL_REGISTRY["fireball"]
        self.assertEqual((fireball.mana_cost, fireball.damage), (5, 12))
        self.assertIsInstance(fireball.classes, tuple)
        self.assertIn("wizard", fireball.classes)
        frost = SPELL_REGISTRY["frost_ray"]
        self.assertEqual((frost.status_effect, frost.duration),
                         ("paralyzed", 2))

    def test_shop_catalogs_load_from_json(self):
        from engine.shop import SHOP_CATALOGS
        self.assertGreaterEqual(len(SHOP_CATALOGS), 10)
        self.assertIn("blacksmith", SHOP_CATALOGS)
        self.assertIn("sword", SHOP_CATALOGS["blacksmith"])

    def test_scroll_spells_exist_in_spell_registry(self):
        from engine.spells import SPELL_REGISTRY
        for item in ITEM_REGISTRY.values():
            spell_id = item.use_effect.get("spell")
            if spell_id:
                self.assertIn(spell_id, SPELL_REGISTRY,
                              f"item {item.id} casts unknown spell "
                              f"'{spell_id}'")

    def test_spell_status_effects_are_known(self):
        from engine.spells import SPELL_REGISTRY
        from characters.status_effects import VALID_EFFECTS
        for spell in SPELL_REGISTRY.values():
            if spell.status_effect:
                self.assertIn(spell.status_effect, VALID_EFFECTS,
                              f"spell {spell.id} applies unknown effect "
                              f"'{spell.status_effect}'")


class TestMonsterData(unittest.TestCase):
    def test_templates_load(self):
        from world.monsters import MONSTER_TEMPLATES
        self.assertGreaterEqual(len(MONSTER_TEMPLATES), 4)
        wolf = MONSTER_TEMPLATES["wolf"]
        self.assertEqual((wolf["hp"], wolf["level"]), (10, 1))

    def test_encounter_table_matches_data(self):
        from world.monsters import encounter_table, MONSTER_TEMPLATES
        table = dict(encounter_table())
        self.assertEqual(table.get("wolf"), 4)
        for tid in table:
            self.assertIn(tid, MONSTER_TEMPLATES)

    def test_dungeon_pool_excludes_non_dungeon_monsters(self):
        from world.monsters import dungeon_pool
        pool = dungeon_pool()
        self.assertIn("goblin", pool)
        self.assertNotIn("wandering_troll", pool)

    def test_build_monster_produces_valid_character(self):
        from world.monsters import build_monster
        troll = build_monster("wandering_troll", (5, 5))
        self.assertEqual(troll.name, "Wandering Troll")
        self.assertEqual(troll.hp, 30)
        self.assertEqual(troll.position, (5, 5))
        self.assertEqual(
            getattr(troll.character_class, "value", ""), "troll")

    def test_build_monster_unknown_falls_back(self):
        from world.monsters import build_monster
        m = build_monster("no_such_monster", (1, 1))
        self.assertEqual(m.name, "Wolf")

    def test_monster_classes_and_races_are_valid_enums(self):
        from world.monsters import MONSTER_TEMPLATES
        from characters.character_types import CharacterClass, CharacterRace
        for tid, spec in MONSTER_TEMPLATES.items():
            CharacterClass(spec.get("class", "monster"))
            CharacterRace(spec.get("race", "goblin"))


class TestQuestAndNpcData(unittest.TestCase):
    def test_quests_load_from_json(self):
        from quests.quest_templates import QUEST_TEMPLATES, create_quest
        self.assertGreaterEqual(len(QUEST_TEMPLATES), 6)
        quest = create_quest("troll_hunt")
        self.assertEqual(quest.reward_gold, 100)
        self.assertEqual(quest.objectives[0].target, "troll_brigand_01")
        # Factories return fresh instances
        self.assertIsNot(create_quest("troll_hunt"), quest)

    def test_quest_givers_exist_in_npc_specs(self):
        from quests.quest_templates import QUEST_TEMPLATES
        from characters.npc_presets import NPC_SPECS
        for qid, factory in QUEST_TEMPLATES.items():
            quest = factory()
            if quest.giver_id:
                self.assertIn(quest.giver_id, NPC_SPECS,
                              f"quest {qid} giver '{quest.giver_id}' "
                              f"is not a preset NPC")

    def test_npc_presets_load_from_json(self):
        from characters.npc_presets import NPC_SPECS, all_presets, make_npc
        self.assertGreaterEqual(len(NPC_SPECS), 11)
        presets = all_presets()
        self.assertEqual(len(presets), len(NPC_SPECS))
        goren = make_npc("tavernkeeper_01")
        self.assertEqual(goren.name, "Goren")
        self.assertEqual(goren.charisma, 16)
        self.assertEqual(goren.home_location, "Oakvale Tavern")
        self.assertTrue(goren.memories)

    def test_troll_position_override(self):
        from characters.npc_presets import make_troll_brigand
        troll = make_troll_brigand(position=(9, 9))
        self.assertEqual(troll.position, (9, 9))
        self.assertEqual(troll.name, "Gorkash")

    def test_npc_classes_races_and_relationships_valid(self):
        from characters.npc_presets import NPC_SPECS
        from characters.character_types import CharacterClass, CharacterRace
        for nid, spec in NPC_SPECS.items():
            CharacterClass(spec.get("class", "villager"))
            CharacterRace(spec.get("race", "human"))
            for other in spec.get("relationships", {}):
                self.assertIn(other, NPC_SPECS,
                              f"NPC {nid} has relationship with unknown "
                              f"NPC '{other}'")

    def test_hostiles_ordered_after_peaceful(self):
        from characters.npc_presets import all_presets
        classes = [getattr(n.character_class, "value", "")
                   for n in all_presets()]
        hostile_ix = [i for i, c in enumerate(classes)
                      if c in ("brigand", "troll", "monster")]
        peaceful_ix = [i for i, c in enumerate(classes)
                       if c not in ("brigand", "troll", "monster")]
        if hostile_ix and peaceful_ix:
            self.assertGreater(min(hostile_ix), max(peaceful_ix))


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
