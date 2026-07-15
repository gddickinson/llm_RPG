"""Round-trip tests for full character/subsystem state persistence (save v3).

Regression tests for the audit finding that equipped gear, metadata (XP,
faction rep, bank, mana, spells), status effects, weather, forage cooldowns,
and companions were silently dropped by save/load.
"""

import shutil
import tempfile
import unittest

from engine.game_engine import GameEngine
from engine.save_load import SaveManager
from characters import equipment as eq
from characters.status_effects import apply_effect, has_effect
from items.item_registry import create_item


class TestFullStateRoundtrip(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.sm = SaveManager(save_dir=self.tmp)
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()
        self.player = self.engine.player

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_equipment_survives_roundtrip(self):
        sword = create_item("longsword")
        self.player.inventory.append(sword)
        eq.equip(self.player, sword)
        self.assertIsNotNone(eq.equipped_weapon(self.player))

        self.sm.save(self.engine, name="rt")
        self.player.equipment = {s: None for s in self.player.equipment}
        self.assertTrue(self.sm.load(self.engine, name="rt"))

        weapon = eq.equipped_weapon(self.engine.player)
        self.assertIsNotNone(weapon, "equipped weapon lost on load")
        self.assertEqual(weapon.name, sword.name)
        # Equipped item must NOT be duplicated back into inventory
        names = [getattr(i, "name", str(i))
                 for i in self.engine.player.inventory]
        self.assertNotIn(sword.name, names)

    def test_metadata_survives_roundtrip(self):
        self.player.metadata["xp"] = 1234
        self.player.metadata["bank"] = 555
        self.player.metadata["mana"] = 7
        self.player.metadata["spells_known"] = ["magic_missile"]
        self.player.metadata.setdefault("faction_rep", {})["guards"] = 42

        self.sm.save(self.engine, name="rt")
        self.player.metadata = {}
        self.assertTrue(self.sm.load(self.engine, name="rt"))

        meta = self.engine.player.metadata
        self.assertEqual(meta.get("xp"), 1234)
        self.assertEqual(meta.get("bank"), 555)
        self.assertEqual(meta.get("mana"), 7)
        self.assertEqual(meta.get("spells_known"), ["magic_missile"])
        self.assertEqual(meta.get("faction_rep", {}).get("guards"), 42)

    def test_status_effects_survive_roundtrip(self):
        apply_effect(self.player, "poisoned", duration=5)
        self.assertTrue(has_effect(self.player, "poisoned"))

        self.sm.save(self.engine, name="rt")
        self.player.metadata["status_effects"] = []
        self.assertTrue(self.sm.load(self.engine, name="rt"))
        self.assertTrue(has_effect(self.engine.player, "poisoned"),
                        "status effect lost on load")

    def test_player_symbol_and_faction_survive(self):
        self.sm.save(self.engine, name="rt")
        self.engine.player.symbol = "?"
        self.assertTrue(self.sm.load(self.engine, name="rt"))
        self.assertEqual(self.engine.player.symbol, "@")

    def test_weather_and_forage_survive_roundtrip(self):
        ws = self.engine.weather_system
        before = ws.to_dict()
        self.engine.forage_manager.harvested_at = {(5, 5): 999}
        self.sm.save(self.engine, name="rt")

        self.engine.forage_manager.harvested_at = {}
        self.assertTrue(self.sm.load(self.engine, name="rt"))
        self.assertEqual(self.engine.weather_system.to_dict(), before)
        self.assertEqual(self.engine.forage_manager.harvested_at.get((5, 5)), 999,
                         "forage cooldowns lost on load")

    def test_shop_stock_survives_roundtrip(self):
        # Build a catalog for some merchant-ish NPC, then consume an item
        npc = next(iter(self.engine.npc_manager.npcs.values()))
        cat = self.engine.shop_manager.catalog_for(npc)
        self.assertTrue(cat.items)
        removed = cat.items.pop(0)
        count_after_sale = len(cat.items)

        self.sm.save(self.engine, name="rt")
        self.engine.shop_manager.catalogs = {}
        self.assertTrue(self.sm.load(self.engine, name="rt"))

        cat2 = self.engine.shop_manager.catalogs.get(npc.id)
        self.assertIsNotNone(cat2, "shop catalog lost on load")
        self.assertEqual(len(cat2.items), count_after_sale,
                         "sold stock reappeared after load")

    def test_dungeon_state_survives_roundtrip(self):
        from world.dungeon import generate_dungeon
        dungeon = generate_dungeon(name="Test Depths", seed=99)
        dungeon.spawned = True
        self.engine.dungeons["test_cave"] = dungeon
        self.engine.current_dungeon = dungeon
        self.engine.dungeon_return_pos = (10, 12)

        self.sm.save(self.engine, name="rt")
        self.engine.dungeons = {}
        self.engine.current_dungeon = None
        self.engine.dungeon_return_pos = None
        self.assertTrue(self.sm.load(self.engine, name="rt"))

        dg = self.engine.dungeons.get("test_cave")
        self.assertIsNotNone(dg, "dungeon lost on load")
        self.assertEqual(dg.name, "Test Depths")
        self.assertTrue(dg.spawned, "dungeon would re-populate monsters")
        self.assertEqual([[c.value for c in row] for row in dg.terrain],
                         [[c.value for c in row] for row in dungeon.terrain])
        self.assertIs(self.engine.current_dungeon, dg)
        self.assertEqual(self.engine.dungeon_return_pos, (10, 12))

    def test_interior_state_survives_roundtrip(self):
        if not self.engine.interiors:
            self.skipTest("no interiors in demo world")
        key, interior = next(iter(self.engine.interiors.items()))
        self.engine.current_interior = interior
        self.engine.exterior_return_pos = (3, 4)

        self.sm.save(self.engine, name="rt")
        self.engine.current_interior = None
        self.engine.exterior_return_pos = None
        self.assertTrue(self.sm.load(self.engine, name="rt"))

        self.assertIs(self.engine.current_interior,
                      self.engine.interiors[key],
                      "player no longer inside the building after load")
        self.assertEqual(self.engine.exterior_return_pos, (3, 4))

    def test_old_save_without_new_keys_still_loads(self):
        """Pre-v3 saves lack metadata/equipment/subsystem keys."""
        self.sm.save(self.engine, name="rt")
        import json
        import os
        path = self.sm.save_path("rt")
        with open(path) as fp:
            data = json.load(fp)
        data["player"].pop("metadata", None)
        data["player"].pop("equipment", None)
        for key in ("weather", "foraging", "companions", "shops",
                    "dungeons", "place_state"):
            data.pop(key, None)
        with open(path, "w") as fp:
            json.dump(data, fp, default=str)

        self.assertTrue(self.sm.load(self.engine, name="rt"))
        self.assertIsInstance(self.engine.player.metadata, dict)


if __name__ == "__main__":
    unittest.main()
