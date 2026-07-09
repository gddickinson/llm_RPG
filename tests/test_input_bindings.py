"""Keybinding regression tests for the play-mode input handler.

Guards against the audit finding that the shop hotkey was bound to S,
which is consumed by move-down first — making the entire shop UI dead
code. Shop now opens on B.
"""

import os
import unittest
from unittest.mock import MagicMock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from engine.game_engine import GameEngine
from ui.input_handler import InputHandler


class FakeEvent:
    def __init__(self, key):
        self.type = pygame.KEYDOWN
        self.key = key
        self.unicode = ""


class FakeGUI:
    """Minimal stand-in for GameGUI: mode flags + spy methods."""

    def __init__(self, engine):
        self.engine = engine
        self.mode = "play"
        self.running = True
        self.overlay = None
        self.inventory_panel = None
        self.shop_panel = None
        self.show_shop = MagicMock()
        self.show_inventory = MagicMock()
        self.show_quests = MagicMock()
        self.show_character_sheet = MagicMock()
        self.show_help = MagicMock()
        self.start_dialog = MagicMock()


class TestShopBinding(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        cls.engine.start_game()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.engine.end_game()
        except Exception:
            pass

    def setUp(self):
        self.gui = FakeGUI(self.engine)
        self.handler = InputHandler(self.engine, self.gui)

    def _adjacent_merchant(self):
        from engine.shop import merchants_near
        merchants = merchants_near(self.engine, self.engine.player, radius=2.0)
        if not merchants:
            # Move a merchant-class NPC next to the player
            for npc in self.engine.npc_manager.npcs.values():
                klass = getattr(npc.character_class, "value", "")
                if klass in ("merchant", "cleric", "wizard", "ranger") \
                        and npc.is_active():
                    px, py = self.engine.player.position
                    npc.position = (px + 1, py)
                    return npc
            self.skipTest("no merchant-class NPC in demo world")
        return merchants[0]

    def test_s_key_moves_down_and_never_opens_shop(self):
        self._adjacent_merchant()
        before = self.engine.player.position
        consumed = self.handler.handle_event(FakeEvent(pygame.K_s))
        self.assertTrue(consumed)
        self.gui.show_shop.assert_not_called()
        after = self.engine.player.position
        # Moved down (or blocked by terrain — but position must not be
        # interpreted as a shop-open either way)
        self.assertIn(after, (before, (before[0], before[1] + 1)))

    def test_b_key_opens_shop_with_adjacent_merchant(self):
        merchant = self._adjacent_merchant()
        consumed = self.handler.handle_event(FakeEvent(pygame.K_b))
        self.assertTrue(consumed)
        self.gui.show_shop.assert_called_once()
        opened_with = self.gui.show_shop.call_args[0][0]
        klass = getattr(opened_with.character_class, "value", "")
        self.assertIn(klass, ("merchant", "cleric", "wizard", "ranger"))

    def test_shop_panel_buy_end_to_end(self):
        """Full flow: open panel, press Enter, item bought, gold spent."""
        from ui.shop_panel import ShopPanel
        merchant = self._adjacent_merchant()
        panel = ShopPanel(self.engine, merchant)
        stock = panel._merchant_items()
        self.assertTrue(stock, "merchant has no stock")
        first = stock[0]
        price = self.engine.shop_manager.buy_price(
            self.engine.player, first, merchant)
        self.engine.player.gold = price + 100
        gold_before = self.engine.player.gold
        inv_before = len(self.engine.player.inventory)

        panel.handle_key(FakeEvent(pygame.K_RETURN))

        self.assertEqual(self.engine.player.gold, gold_before - price)
        self.assertEqual(len(self.engine.player.inventory), inv_before + 1)

    def test_b_key_without_merchant_logs_message(self):
        # Teleport player far from everyone
        self.engine.player.position = (1, 1)
        for npc in self.engine.npc_manager.npcs.values():
            if npc.position == (1, 1) or npc.position == (2, 1):
                npc.position = (50, 50)
        self.handler.handle_event(FakeEvent(pygame.K_b))
        self.gui.show_shop.assert_not_called()


if __name__ == "__main__":
    unittest.main()
