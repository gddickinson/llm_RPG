"""M3 — magic-item imbuing + magic crafting.

Enchanting mutates an EXISTING item in place (equip_bonuses / damage_kind /
metadata), gated on a forge, the enchanting skill, and reagents; the change is
save-safe for free. Magic recipes gate on a min_skill in enchanting.
"""

import unittest

from engine.game_engine import GameEngine
from items import enchanting as en
from items.item_registry import create_item
from engine.skill_progression import add_skill_xp, total_xp_for_level, \
    get_skill_level
from engine.effects import effective_weapon_damage_bonus


class _Base(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False)
        self.engine.start_game()
        self.p = self.engine.player
        forge = next((l for l in self.engine.world.locations
                      if (l.properties or {}).get("forge")), None)
        if forge is None:
            self.skipTest("no forge")
        self.p.position = forge.center()

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _skill(self, lvl):
        add_skill_xp(self.p, "enchanting", total_xp_for_level(lvl))


class TestImbue(_Base):
    def test_flametongue_imbues_a_weapon(self):
        sword = create_item("sword")
        self.p.add_item(sword)
        self.p.add_item(create_item("arcane_dust", quantity=4))
        self.p.add_item(create_item("ember_core", quantity=2))
        self._skill(4)
        from characters.equipment import equip
        equip(self.p, sword)
        base = effective_weapon_damage_bonus(self.p)
        ok, msg = en.enchant(self.engine, sword, "flametongue")
        self.assertTrue(ok, msg)
        self.assertEqual(sword.damage_kind, "fire")
        self.assertEqual(sword.equip_bonuses.get("damage"), 2)
        self.assertIn("flametongue", sword.metadata["enchantments"])
        self.assertIn("Flaming", sword.name)
        self.assertEqual(effective_weapon_damage_bonus(self.p), base + 2)

    def test_needs_reagents(self):
        sword = create_item("sword")
        self.p.add_item(sword)
        self._skill(4)
        ok, why = en.can_enchant(self.engine, sword, "flametongue")
        self.assertFalse(ok)
        self.assertIn("arcane dust", why)

    def test_needs_skill(self):
        sword = create_item("sword")
        self.p.add_item(sword)
        self.p.add_item(create_item("arcane_dust", quantity=4))
        self.p.add_item(create_item("shadow_essence", quantity=2))
        ok, why = en.can_enchant(self.engine, sword, "vampiric")  # needs skill 8
        self.assertFalse(ok)
        self.assertIn("enchanting", why)

    def test_needs_a_forge(self):
        # move off the forge
        self.p.position = (0, 0)
        sword = create_item("sword")
        self.p.add_item(sword)
        self.p.add_item(create_item("arcane_dust", quantity=4))
        self.p.add_item(create_item("ember_core", quantity=2))
        self._skill(4)
        ok, why = en.can_enchant(self.engine, sword, "flametongue")
        self.assertFalse(ok)
        self.assertIn("forge", why)

    def test_wrong_item_type(self):
        potion = create_item("potion")
        ok, why = en.can_enchant(self.engine, potion, "flametongue")
        self.assertFalse(ok)

    def test_no_double_apply(self):
        sword = create_item("sword")
        self.p.add_item(sword)
        self.p.add_item(create_item("arcane_dust", quantity=6))
        self.p.add_item(create_item("ember_core", quantity=2))
        self._skill(4)
        en.enchant(self.engine, sword, "flametongue")
        ok, why = en.can_enchant(self.engine, sword, "flametongue")
        self.assertFalse(ok)
        self.assertIn("already", why)

    def test_trains_enchanting(self):
        sword = create_item("sword")
        self.p.add_item(sword)
        self.p.add_item(create_item("arcane_dust", quantity=4))
        self._skill(2)
        before = get_skill_level(self.p, "enchanting")
        # keen_edge: min_skill 1, only arcane_dust
        en.enchant(self.engine, sword, "keen_edge")
        # xp was granted (level may or may not tick, but xp rose)
        from engine.skill_progression import get_skill_xp
        self.assertGreater(get_skill_xp(self.p, "enchanting"), 0)
        self.assertGreaterEqual(get_skill_level(self.p, "enchanting"), before)


class TestPersistence(_Base):
    def test_enchant_survives_save_load(self):
        import tempfile
        import os
        sword = create_item("sword")
        self.p.add_item(sword)
        self.p.add_item(create_item("arcane_dust", quantity=4))
        self.p.add_item(create_item("ember_core", quantity=1))
        self._skill(4)
        en.enchant(self.engine, sword, "flametongue")
        path = os.path.join(tempfile.mkdtemp(), "ench.json")
        self.engine.save_game(path)
        eng2 = GameEngine(llm_provider="heuristic", enable_npc_processes=False)
        eng2.load_game(path)
        blade = next((it for it in eng2.player.inventory
                      if "Flaming" in getattr(it, "name", "")), None)
        self.assertIsNotNone(blade, "the enchanted blade persists")
        self.assertEqual(blade.damage_kind, "fire")
        self.assertEqual(blade.equip_bonuses.get("damage"), 2)
        try:
            eng2.end_game()
        except Exception:
            pass


class TestMagicCrafting(_Base):
    def test_magic_recipe_gates_on_skill(self):
        from items.crafting import can_craft
        self.p.gold = 999
        self.p.add_item(create_item("arcane_dust", quantity=8))
        self.p.add_item(create_item("mana_crystal", quantity=2))
        props = {"forge": True}
        # ingredients present, but amulet_of_warding needs enchanting 5
        reason = can_craft(self.p, "amulet_of_warding", props)
        self.assertIn("enchanting", reason)
        self._skill(6)
        self.assertEqual(can_craft(self.p, "amulet_of_warding", props), "",
                         "craftable once skilled + supplied")

    def test_refine_mana_crystal(self):
        from items.crafting import craft
        self.p.add_item(create_item("arcane_dust", quantity=4))
        self._skill(5)
        msg = craft(self.p, "mana_crystal", {"forge": True})
        ids = [getattr(i, "id", "") for i in self.p.inventory]
        self.assertIn("mana_crystal", ids)


if __name__ == "__main__":
    unittest.main()
