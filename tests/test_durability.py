"""Gear durability + repair — the perpetual sink (P2.3)."""

import unittest

from engine.game_engine import GameEngine
from engine.durability import (
    is_degradable, get_durability, degrade, is_broken, repair,
    repair_cost, durability_label, WEAPON_MAX,
)
from items.item_registry import create_item
from characters import equipment as eq


class TestDurability(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()
        self.player = self.engine.player

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_commons_never_degrade(self):
        sword = create_item("sword")  # common rarity
        self.assertFalse(is_degradable(sword))
        self.assertIsNone(get_durability(sword))
        self.assertIsNone(degrade(sword))

    def test_rare_weapon_degrades_and_breaks(self):
        blade = create_item("silver_blade")  # rare
        self.assertTrue(is_degradable(blade))
        self.assertEqual(get_durability(blade), WEAPON_MAX)
        msg = None
        for _ in range(WEAPON_MAX):
            msg = degrade(blade)
        self.assertTrue(is_broken(blade))
        self.assertIn("breaks", msg)
        self.assertEqual(durability_label(blade), " [BROKEN]")

    def test_broken_weapon_deals_unarmed_damage(self):
        blade = create_item("silver_blade")
        self.player.inventory.append(blade)
        eq.equip(self.player, blade)
        self.assertEqual(
            self.engine.combat_system._best_weapon_damage(self.player),
            blade.damage)
        blade.metadata["durability"] = 0
        self.assertEqual(
            self.engine.combat_system._best_weapon_damage(self.player), 1)

    def test_broken_armor_gives_no_ac(self):
        from engine.effects import effective_ac
        mail = create_item("chainmail")  # uncommon
        self.player.inventory.append(mail)
        eq.equip(self.player, mail)
        with_armor = effective_ac(self.player)
        mail.metadata["durability"] = 0
        self.assertLess(effective_ac(self.player), with_armor)

    def test_combat_hit_wears_attacker_weapon(self):
        blade = create_item("silver_blade")
        self.player.inventory.append(blade)
        eq.equip(self.player, blade)
        wolf = None
        from world.monsters import build_monster
        px, py = self.player.position
        wolf = build_monster("wolf", (px + 1, py))
        self.engine.npc_manager.add_npc(wolf)
        before = get_durability(blade)
        # Attack until one lands (rng)
        for _ in range(30):
            self.engine.combat_system.player_attack(wolf.name)
            if get_durability(blade) < before or not wolf.is_active():
                break
        self.assertLessEqual(get_durability(blade), before)

    def test_repair_needs_forge_and_gold(self):
        blade = create_item("silver_blade")
        blade.metadata["durability"] = 50
        self.player.gold = 0
        self.assertIn("forge", repair(self.player, blade, False).lower())
        cost = repair_cost(blade)
        self.assertGreater(cost, 0)
        msg = repair(self.player, blade, True)
        self.assertIn("cost", msg.lower())
        self.player.gold = cost + 10
        msg = repair(self.player, blade, True)
        self.assertIn("repair", msg.lower())
        self.assertEqual(get_durability(blade), WEAPON_MAX)
        self.assertEqual(self.player.gold, 10)

    def test_durability_persists_in_saves(self):
        import shutil
        import tempfile
        from engine.save_load import SaveManager
        blade = create_item("silver_blade")
        blade.metadata["durability"] = 42
        self.player.inventory.append(blade)
        eq.equip(self.player, blade)
        tmp = tempfile.mkdtemp()
        try:
            sm = SaveManager(save_dir=tmp)
            sm.save(self.engine, name="d")
            self.assertTrue(sm.load(self.engine, name="d"))
            loaded = eq.equipped_weapon(self.engine.player)
            self.assertEqual(loaded.metadata.get("durability"), 42)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_sword_recipe_consumes_iron_bars(self):
        from items.crafting import craft
        self.player.gold = 50
        self.player.inventory.append(create_item("iron_bar", quantity=2))
        msg = craft(self.player, "sword", {"forge": True})
        self.assertIn("craft", msg.lower())
        ids = [getattr(i, "id", "") for i in self.player.inventory]
        self.assertIn("sword", ids)
        self.assertNotIn("iron_bar", ids)


if __name__ == "__main__":
    unittest.main()
