"""Trade info (PUX.2): the numbers behind a merchant deal — item
reports, compare-to-equipped, price transparency, and bulk maths."""

import os as _os
import tempfile as _tempfile
import types
import unittest

_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_lib_"))

from engine import trade_info                       # noqa: E402
from engine.game_engine import GameEngine           # noqa: E402
from items.item import Item, ItemRarity, ItemType   # noqa: E402
from items.item_registry import create_item         # noqa: E402


class TestPureHelpers(unittest.TestCase):
    def test_item_report_weapon(self):
        blade = create_item("sword")
        lines = trade_info.item_report(blade)
        self.assertTrue(any("Damage" in ln for ln in lines))
        self.assertTrue(any("Value" in ln for ln in lines))

    def test_item_report_consumable(self):
        potion = create_item("potion")
        lines = trade_info.item_report(potion)
        self.assertTrue(lines and potion.name in lines[0])

    def test_is_junk_only_common_misc_trinkets(self):
        trinket = Item(id="trinket", name="Trinket",
                       item_type=ItemType.MISC,
                       rarity=ItemRarity.COMMON, value=5)
        self.assertTrue(trade_info.is_junk(trinket))
        blade = create_item("sword")            # gear is never junk
        self.assertFalse(trade_info.is_junk(blade))
        precious = Item(id="gem", name="Gem", item_type=ItemType.MISC,
                        rarity=ItemRarity.COMMON, value=500)
        self.assertFalse(trade_info.is_junk(precious))   # too valuable

    def test_junk_items_filters_inventory(self):
        trinket = Item(id="t", name="T", item_type=ItemType.MISC,
                       rarity=ItemRarity.COMMON, value=3)
        player = types.SimpleNamespace(
            inventory=[trinket, create_item("sword")])
        self.assertEqual(trade_info.junk_items(player), [trinket])

    def test_affordable_qty(self):
        player = types.SimpleNamespace(gold=100)
        self.assertEqual(
            trade_info.affordable_qty(player, 30, available=10, want=5), 3)
        self.assertEqual(
            trade_info.affordable_qty(player, 30, available=2, want=5), 2)
        self.assertEqual(
            trade_info.affordable_qty(player, 0, available=9, want=5), 5)

    def test_factors_line_formats(self):
        self.assertEqual(trade_info.factors_line([]), "at base value")
        self.assertIn("x1.20",
                      trade_info.factors_line([("stock", 1.2)]))


class TestWithEngine(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False)
        self.engine.start_game()

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_compare_to_equipped(self):
        from items.item import ItemType as IT
        weak = Item(id="stick", name="Stick", item_type=IT.WEAPON,
                    damage=2, value=1)
        strong = Item(id="greatsword", name="Greatsword",
                      item_type=IT.WEAPON, damage=12, value=1)
        from characters.equipment import equip
        equip(self.engine.player, weak)
        line = trade_info.compare_to_equipped(self.engine, strong)
        self.assertIsNotNone(line)
        self.assertIn("dmg", line)
        self.assertIn("+", line)             # the greatsword is better

    def test_compare_none_for_non_equipment(self):
        potion = create_item("potion")
        self.assertIsNone(
            trade_info.compare_to_equipped(self.engine, potion))

    def test_price_factors_returns_a_list(self):
        from characters.npc_presets import make_npc
        merchant = make_npc("blacksmith_01", self.engine.player.position)
        self.engine.npc_manager.add_npc(merchant)
        item = create_item("sword")
        factors = trade_info.price_factors(
            self.engine.shop_manager, self.engine.player, item,
            merchant, selling=False)
        self.assertIsInstance(factors, list)
        for label, mult in factors:          # each deviates from base
            self.assertNotAlmostEqual(mult, 1.0, places=2)


if __name__ == "__main__":
    unittest.main()
