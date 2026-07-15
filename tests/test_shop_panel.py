"""Trading II (PUX.2): the enriched shop panel — bulk buy/sell, a
sell-all-junk sweep, an inspect selection, and a crash-free draw."""

import os as _os
import tempfile as _tempfile
import unittest

_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_lib_"))

import pygame                                        # noqa: E402

from engine.game_engine import GameEngine           # noqa: E402
from characters.npc_presets import make_npc         # noqa: E402
from items.item import Item, ItemRarity, ItemType   # noqa: E402
from ui.shop_panel import ShopPanel                 # noqa: E402


class TestShopPanel(unittest.TestCase):
    def setUp(self):
        pygame.display.init()
        pygame.display.set_mode((1024, 700))
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False)
        self.engine.start_game()
        self.merchant = make_npc("blacksmith_01",
                                 self.engine.player.position)
        self.engine.npc_manager.add_npc(self.merchant)
        self.panel = ShopPanel(self.engine, self.merchant)
        self.cat = self.engine.shop_manager.catalog_for(self.merchant)

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_wares_are_stocked(self):
        self.assertTrue(self.cat.items, "the smith has wares")

    def test_bulk_buy_takes_five(self):
        self.engine.player.gold = 9999
        n0 = len(self.engine.player.inventory)
        self.panel.column = 0
        self.panel.cursor_left = 0
        self.panel._transact(5)
        self.assertEqual(len(self.engine.player.inventory) - n0, 5,
                         "Shift+Enter buys a stack of five")

    def test_bulk_buy_stops_when_broke(self):
        # only afford a couple, not the whole five
        item = self.cat.items[0]
        price = self.engine.shop_manager.buy_price(
            self.engine.player, item, self.merchant)
        self.engine.player.gold = price * 2 + 1
        n0 = len(self.engine.player.inventory)
        self.panel.column = 0
        self.panel.cursor_left = 0
        self.panel._transact(5)
        self.assertLessEqual(len(self.engine.player.inventory) - n0, 2,
                             "a bulk buy halts when the purse runs dry")

    def test_sell_all_junk_clears_trinkets(self):
        for i in range(3):
            self.engine.player.inventory.append(
                Item(id=f"j{i}", name=f"Junk{i}",
                     item_type=ItemType.MISC,
                     rarity=ItemRarity.COMMON, value=2))
        self.cat.gold = 9999
        junk_before = sum(1 for it in self.engine.player.inventory
                          if it.item_type == ItemType.MISC
                          and it.value <= 25)
        self.assertGreaterEqual(junk_before, 3)
        self.panel._sell_all_junk()
        junk_after = sum(1 for it in self.engine.player.inventory
                         if it.item_type == ItemType.MISC
                         and it.value <= 25)
        self.assertEqual(junk_after, 0, "the junk was cleared out")

    def test_selected_item_follows_the_cursor(self):
        self.panel.column = 0
        self.panel.cursor_left = 0
        self.assertIs(self.panel._selected_item(), self.cat.items[0])

    def test_draw_does_not_crash(self):
        surf = pygame.Surface((1024, 700))
        self.panel.draw(surf, surf.get_rect())     # includes inspect pane


if __name__ == "__main__":
    unittest.main()
