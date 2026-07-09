"""Tests for the crafting panel (K) — the first UI access to crafting."""

import os
import unittest
from unittest.mock import MagicMock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from engine.game_engine import GameEngine
from items.item_registry import create_item
from ui.crafting_panel import CraftingPanel
from ui.input_handler import InputHandler


class FakeEvent:
    def __init__(self, key):
        self.type = pygame.KEYDOWN
        self.key = key
        self.unicode = ""


class TestCraftingPanel(unittest.TestCase):
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
        self.panel = CraftingPanel(self.engine)
        self.player = self.engine.player

    def test_rows_lists_all_recipes(self):
        from items.crafting import RECIPES
        rows = self.panel.rows()
        self.assertEqual(len(rows), len(RECIPES))

    def test_craftable_recipes_sort_first(self):
        self.player.inventory.append(create_item("herb_bundle"))
        self.player.gold = 100
        rows = self.panel.rows()
        reasons = [bool(reason) for _, reason in rows]
        # Once a blocked recipe appears, no craftable one may follow
        if True in reasons and False in reasons:
            self.assertLess(reasons.index(False), reasons.index(True))
            self.assertEqual(reasons, sorted(reasons))

    def test_craft_through_panel_end_to_end(self):
        """Cursor onto the potion recipe, press Enter, potion appears."""
        self.player.inventory.append(create_item("herb_bundle"))
        self.player.gold = 50
        gold_before = self.player.gold

        rows = self.panel.rows()
        idx = next(i for i, (r, _) in enumerate(rows)
                   if r.output_id == "potion")
        self.panel.cursor = idx
        self.panel.handle_key(FakeEvent(pygame.K_RETURN))

        names = [getattr(i, "id", "") for i in self.player.inventory]
        self.assertIn("potion", names)
        self.assertEqual(self.player.gold, gold_before - 5)
        self.assertNotIn("herb_bundle", names, "ingredient not consumed")

    def test_forge_recipe_blocked_away_from_forge(self):
        self.player.gold = 1000
        self.player.inventory.append(create_item("coins", quantity=10))
        rows = dict((r.output_id, reason) for r, reason in self.panel.rows())
        self.assertIn("forge", rows["sword"].lower(),
                      "sword should require a forge")

    def test_ingredient_line_shows_have_need(self):
        from items.crafting import find_recipe
        line = self.panel._ingredient_line(find_recipe("potion"))
        self.assertRegex(line, r"\d/1 Bundle of Herbs")
        self.assertIn("5g", line)


class TestCraftingBinding(unittest.TestCase):
    def setUp(self):
        self.engine = TestCraftingPanel.engine if hasattr(
            TestCraftingPanel, "engine") else None
        if self.engine is None:
            self.engine = GameEngine(
                llm_provider="heuristic", enable_npc_processes=False)
            self.engine.start_game()
        self.gui = MagicMock()
        self.gui.mode = "play"
        self.handler = InputHandler(self.engine, self.gui)

    def test_k_opens_crafting(self):
        self.handler.handle_event(FakeEvent(pygame.K_k))
        self.gui.show_crafting.assert_called_once()

    def test_escape_closes_crafting_mode(self):
        self.gui.mode = "crafting"
        self.gui.crafting_panel = CraftingPanel(self.engine)
        self.handler.handle_event(FakeEvent(pygame.K_ESCAPE))
        self.assertEqual(self.gui.mode, "play")


if __name__ == "__main__":
    unittest.main()
