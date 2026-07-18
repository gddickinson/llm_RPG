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
        self.show_build_planner = MagicMock()   # M5: B off a merchant = build
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
        # M5: away from a merchant, B opens the build/terraform tool instead
        self.gui.show_build_planner.assert_called_once()


class TestDiagonalMovement(unittest.TestCase):
    """The numpad walks all 8 ways — the fix for 'no diagonal
    interactions' (the letter-corner keys are taken, so diagonals live on
    the numpad)."""

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
        from world.world_map import TerrainType
        self.gui = FakeGUI(self.engine)
        self.handler = InputHandler(self.engine, self.gui)
        # a clear patch of open ground to step around on
        self.ox, self.oy = 6, 6
        wmap = self.engine.world.map
        for yy in range(self.oy - 2, self.oy + 3):
            for xx in range(self.ox - 2, self.ox + 3):
                wmap.terrain[yy][xx] = TerrainType.GRASS
        wmap.remove_character(self.engine.player)
        self.engine.player.position = (self.ox, self.oy)
        wmap.place_character(self.engine.player, self.ox, self.oy)
        # a movement-key test, not a combat one: silence every ambient
        # spawner (P32.1/2 packs, P32.3 wildlife) and clear anything already
        # loitering on the walk area so nothing bodyblocks a step-target tile
        self.engine.encounter_manager.maybe_spawn = lambda: None
        self.engine.wildlife.update = lambda: None
        for n in list(self.engine.npc_manager.npcs.values()):
            if abs(n.position[0] - self.ox) <= 3 and \
                    abs(n.position[1] - self.oy) <= 3:
                wmap.remove_character(n)

    def _press(self, key):
        # the world ticks between presses (advance_turn), so a distant NPC can
        # wander onto a step-target tile; re-clear the immediate ring each time
        # so the movement key — not a bodyblock — is what we're testing
        wmap = self.engine.world.map
        for n in list(self.engine.npc_manager.npcs.values()):
            if abs(n.position[0] - self.ox) <= 1 and \
                    abs(n.position[1] - self.oy) <= 1:
                wmap.remove_character(n)
        self.engine.player.position = (self.ox, self.oy)
        self.handler.handle_event(FakeEvent(key))
        return self.engine.player.position

    def test_numpad_diagonals_step_diagonally(self):
        cases = {pygame.K_KP9: (1, -1), pygame.K_KP7: (-1, -1),
                 pygame.K_KP3: (1, 1), pygame.K_KP1: (-1, 1)}
        for key, (dx, dy) in cases.items():
            self.assertEqual(self._press(key),
                             (self.ox + dx, self.oy + dy),
                             f"numpad {key} should step ({dx},{dy})")

    def test_numpad_orthogonals_also_move(self):
        self.assertEqual(self._press(pygame.K_KP6), (self.ox + 1, self.oy))
        self.assertEqual(self._press(pygame.K_KP8), (self.ox, self.oy - 1))

    def test_numpad_five_waits_in_place(self):
        t0 = self.engine.turn_counter
        pos = self._press(pygame.K_KP5)
        self.assertEqual(pos, (self.ox, self.oy), "you hold your ground")
        self.assertGreater(self.engine.turn_counter, t0, "but time passes")


if __name__ == "__main__":
    unittest.main()
