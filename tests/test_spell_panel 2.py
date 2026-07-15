"""Spellbook panel + spell growth tests (P5.2)."""

import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from engine.game_engine import GameEngine
from engine.spells import SPELL_REGISTRY, ensure_mana
from items.item_registry import create_item
from ui.spell_panel import SpellPanel


class FakeEvent:
    def __init__(self, key):
        self.type = pygame.KEYDOWN
        self.key = key
        self.unicode = ""


class TestSpellGrowth(unittest.TestCase):
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

    def test_fifteen_spells_defined(self):
        self.assertGreaterEqual(len(SPELL_REGISTRY), 15)
        for sid in ("firebolt", "smite", "entangle", "drain",
                    "regrowth", "hex", "frost_armor"):
            self.assertIn(sid, SPELL_REGISTRY)

    def test_tome_teaches_spell(self):
        ensure_mana(self.player)
        self.assertNotIn("firebolt",
                         self.player.metadata.get("spells_known", []))
        self.player.inventory.append(create_item("tome_firebolt"))
        msg = self.engine.use_item("Primer of Flame")
        self.assertIn("learn", msg.lower())
        self.assertIn("firebolt", self.player.metadata["spells_known"])
        ids = [getattr(i, "id", "") for i in self.player.inventory]
        self.assertNotIn("tome_firebolt", ids, "tome consumed")

    def test_tome_refused_if_already_known(self):
        ensure_mana(self.player)
        self.player.metadata.setdefault(
            "spells_known", []).append("firebolt")
        self.player.inventory.append(create_item("tome_firebolt"))
        msg = self.engine.use_item("Primer of Flame")
        self.assertIn("already know", msg)
        ids = [getattr(i, "id", "") for i in self.player.inventory]
        self.assertIn("tome_firebolt", ids, "tome must not be wasted")


class TestSpellPanel(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()
        self.player = self.engine.player
        ensure_mana(self.player)
        self.player.metadata["spells_known"] = ["heal", "firebolt"]
        self.player.metadata["mana"] = 10
        self.player.metadata["max_mana"] = 10
        self.panel = SpellPanel(self.engine)

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_panel_lists_known_spells(self):
        names = [s.id for s in self.panel.spells()]
        self.assertEqual(set(names), {"heal", "firebolt"})

    def test_enter_casts_selected_heal_on_self(self):
        self.player.hp = self.player.max_hp - 10
        idx = [s.id for s in self.panel.spells()].index("heal")
        self.panel.cursor = idx
        self.panel.handle_key(FakeEvent(pygame.K_RETURN))
        self.assertGreater(self.player.hp, self.player.max_hp - 10)
        self.assertLess(self.player.metadata["mana"], 10)

    def test_number_key_quick_casts(self):
        self.player.hp = self.player.max_hp - 10
        idx = [s.id for s in self.panel.spells()].index("heal")
        self.panel.handle_key(FakeEvent(pygame.K_1 + idx))
        self.assertGreater(self.player.hp, self.player.max_hp - 10)

    def test_attack_spell_hits_nearest_hostile(self):
        from world.monsters import build_monster
        px, py = self.player.position
        wolf = build_monster("wolf", (px + 2, py))
        self.engine.npc_manager.add_npc(wolf)
        hp_before = wolf.hp
        idx = [s.id for s in self.panel.spells()].index("firebolt")
        self.panel.cursor = idx
        self.panel.handle_key(FakeEvent(pygame.K_RETURN))
        self.assertLess(wolf.hp, hp_before)

    def test_x_opens_spellbook(self):
        from unittest.mock import MagicMock
        from ui.input_handler import InputHandler
        gui = MagicMock()
        gui.mode = "play"
        handler = InputHandler(self.engine, gui)
        handler.handle_event(FakeEvent(pygame.K_x))
        gui.show_spellbook.assert_called_once()


if __name__ == "__main__":
    unittest.main()
