"""Audit fix (A-trap): the home chest no longer loses items.

Deposit worked but there was no way to SEE or WITHDRAW stored goods (the audit's
item-loss trap). Now the inventory panel shows a Home Chest section and [H] on a
chest row takes the item back.
"""

import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
import tempfile
os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                      tempfile.mkdtemp(prefix="llmrpg_chest_"))

import unittest

import pygame

from items.item_registry import create_item
from engine import homestead


class TestHomeChest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    def _engine_with_home(self):
        from engine.game_engine import GameEngine
        eng = GameEngine(llm_provider="heuristic", enable_npc_processes=False)
        eng.start_game()
        eng.player.metadata["home"] = "Test Cottage"
        eng.player.metadata["home_ready"] = True
        eng.player.inventory = []
        return eng

    def test_stored_items_show_in_the_panel(self):
        from ui.inventory_panel import InventoryPanel
        eng = self._engine_with_home()
        try:
            eng.player.inventory = [create_item("sword")]
            eng.home_deposit("Iron Sword")
            rows = InventoryPanel(eng).rows()
            chest = [r for r in rows if r[0] == "chest"]
            self.assertEqual(len(chest), 1)
            self.assertEqual(chest[0][2].name, "Iron Sword")
            self.assertTrue(any(r[0] == "sep" and "Chest" in r[1]
                                for r in rows), "a Home Chest header shows")
        finally:
            eng.end_game()

    def test_withdraw_via_the_panel_returns_the_item(self):
        from ui.inventory_panel import InventoryPanel
        eng = self._engine_with_home()
        try:
            eng.player.inventory = [create_item("sword")]
            eng.home_deposit("Iron Sword")
            self.assertEqual(len(eng.player.inventory), 0)
            panel = InventoryPanel(eng)
            rows = panel.rows()
            chest_row = next(r for r in rows if r[0] == "chest")
            panel.cursor = rows.index(chest_row)
            panel._store(rows)                         # [H] on a chest row
            self.assertTrue(any(getattr(it, "name", "") == "Iron Sword"
                                for it in eng.player.inventory))
            self.assertEqual(homestead.stored_names(eng.player), [])
        finally:
            eng.end_game()

    def test_deposit_and_withdraw_round_trip_preserves_quantity(self):
        eng = self._engine_with_home()
        try:
            eng.player.inventory = [create_item("arrow", quantity=20)]
            eng.home_deposit("Arrows")
            eng.home_withdraw("Arrows")
            arrows = [it for it in eng.player.inventory
                      if getattr(it, "id", "") == "arrow"]
            self.assertEqual(sum(a.quantity for a in arrows), 20)
        finally:
            eng.end_game()

    def test_no_chest_section_without_a_home(self):
        from ui.inventory_panel import InventoryPanel
        from engine.game_engine import GameEngine
        eng = GameEngine(llm_provider="heuristic", enable_npc_processes=False)
        eng.start_game()
        try:
            eng.player.metadata.pop("home_ready", None)
            rows = InventoryPanel(eng).rows()
            self.assertFalse(any(r[0] == "chest" for r in rows))
        finally:
            eng.end_game()


if __name__ == "__main__":
    unittest.main()
