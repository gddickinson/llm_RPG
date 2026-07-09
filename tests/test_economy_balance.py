"""Economy balancing (P2.4): finite merchant gold, daily restock,
bounded sell-loops."""

import unittest
from unittest.mock import MagicMock

import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from engine.game_engine import GameEngine
from items.item_registry import create_item
from ui.shop_panel import ShopPanel


class FakeEvent:
    def __init__(self, key):
        self.type = pygame.KEYDOWN
        self.key = key
        self.unicode = ""


def _any_merchant(engine):
    for npc in engine.npc_manager.npcs.values():
        klass = getattr(npc.character_class, "value", "")
        if klass in ("merchant", "cleric", "wizard", "ranger") and \
                npc.is_active():
            return npc
    return None


class TestEconomyBalance(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()
        self.player = self.engine.player
        self.merchant = _any_merchant(self.engine)
        if self.merchant is None:
            self.skipTest("no merchant in demo world")
        self.cat = self.engine.shop_manager.catalog_for(self.merchant)

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_merchant_has_finite_gold(self):
        self.assertGreater(self.cat.gold, 0)
        self.assertLess(self.cat.gold, 10_000)

    def test_selling_is_bounded_by_merchant_gold(self):
        panel = ShopPanel(self.engine, self.merchant)
        panel.column = 1
        self.cat.gold = 5  # nearly broke merchant
        # Player has an expensive item to sell
        blade = create_item("silver_blade")  # value 200, sell ~100
        self.player.inventory = [blade]
        gold_before = self.player.gold
        panel._transact()
        self.assertEqual(self.player.gold, gold_before,
                         "sale should be refused when merchant is broke")
        self.assertIn(blade, self.player.inventory)

    def test_selling_drains_merchant_and_buying_refills(self):
        panel = ShopPanel(self.engine, self.merchant)
        # Sell a potion
        potion = create_item("potion")
        self.player.inventory = [potion]
        panel.column = 1
        merchant_gold = self.cat.gold
        panel._transact()
        self.assertLess(self.cat.gold, merchant_gold,
                        "selling should drain the merchant's purse")
        # Buy something back
        drained = self.cat.gold
        self.player.gold = 1000
        panel.column = 0
        panel.cursor_left = 0
        panel._transact()
        self.assertGreater(self.cat.gold, drained,
                           "buying should refill the merchant's purse")

    def test_daily_restock_replenishes_stock_and_gold(self):
        # Deplete
        self.cat.items = []
        self.cat.gold = 0
        # Not due yet
        self.engine.shop_manager.refresh_all_if_due()
        self.assertEqual(self.cat.items, [])
        # Jump a day ahead
        self.engine.world.time += 24 * 60 + 1
        self.engine.shop_manager.refresh_all_if_due()
        self.assertTrue(self.cat.items, "stock should refresh after a day")
        self.assertGreater(self.cat.gold, 0)

    def test_restock_is_wired_into_the_turn_loop(self):
        self.cat.items = []
        self.engine.world.time += 24 * 60 + 1
        # advance_turn checks every 30 turns
        for _ in range(31):
            self.engine.advance_turn()
        self.assertTrue(self.cat.items,
                        "advance_turn should trigger daily restock")

    def test_merchant_gold_persists_in_saves(self):
        import shutil
        import tempfile
        from engine.save_load import SaveManager
        self.cat.gold = 77
        tmp = tempfile.mkdtemp()
        try:
            sm = SaveManager(save_dir=tmp)
            sm.save(self.engine, name="e")
            self.cat.gold = 0
            self.assertTrue(sm.load(self.engine, name="e"))
            cat = self.engine.shop_manager.catalogs[self.merchant.id]
            self.assertEqual(cat.gold, 77)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
