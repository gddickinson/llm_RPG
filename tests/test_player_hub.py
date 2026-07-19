"""The unified Character Hub (GAP.6): pure content builders, the
paper-doll drop logic, and the tabbed screen open/close/switch + a
headless draw of every tab."""

import unittest

import pygame

from engine.game_engine import GameEngine
from ui import hub_data
from ui import hub_paperdoll as doll
from items.item_registry import create_item


class TestHubData(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False)
        self.engine.start_game()

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_every_builder_returns_lines(self):
        for fn in (hub_data.character_lines, hub_data.skills_lines,
                   hub_data.spells_lines, hub_data.quests_lines,
                   hub_data.journal_lines):
            lines = fn(self.engine)
            self.assertIsInstance(lines, list)
            self.assertTrue(lines)
            self.assertTrue(all(isinstance(x, str) for x in lines))

    def test_character_lines_report_identity_and_stats(self):
        lines = "\n".join(hub_data.character_lines(self.engine))
        self.assertIn(self.engine.player.name, lines)
        self.assertIn("ATTRIBUTES", lines)
        self.assertIn("STR", lines)


class TestPaperdollDrop(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False)
        self.engine.start_game()
        self.p = self.engine.player

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_drag_bag_item_to_slot_equips(self):
        sword = create_item("sword")
        self.p.inventory.append(sword)
        idx = len(self.p.inventory) - 1  # identity, not equality (dup swords)
        from characters import equipment as eqp
        msg = doll.apply_drop(self.engine, ("bag", idx), ("slot", "weapon"))
        self.assertTrue(msg)
        self.assertIs(eqp.get_equipment(self.p).get("weapon"), sword)

    def test_incompatible_slot_rejects(self):
        sword = create_item("sword")
        self.p.inventory.append(sword)
        idx = len(self.p.inventory) - 1  # identity, not equality (dup swords)
        from characters import equipment as eqp
        doll.apply_drop(self.engine, ("bag", idx), ("slot", "boots"))
        self.assertIsNone(eqp.get_equipment(self.p).get("boots"))

    def test_drag_slot_to_bag_unequips(self):
        from characters import equipment as eqp
        sword = create_item("sword")
        self.p.inventory.append(sword)
        eqp.equip(self.p, sword)
        self.assertIsNotNone(eqp.get_equipment(self.p).get("weapon"))
        doll.apply_drop(self.engine, ("slot", "weapon"), ("bag", -1))
        self.assertIsNone(eqp.get_equipment(self.p).get("weapon"))

    def test_click_equips_a_bag_item(self):
        from characters import equipment as eqp
        sword = create_item("sword")
        self.p.inventory.append(sword)
        idx = len(self.p.inventory) - 1  # identity, not equality (dup swords)
        # a plain click (origin == target) on a bag item equips it
        doll.apply_drop(self.engine, ("bag", idx), ("bag", idx))
        self.assertIs(eqp.get_equipment(self.p).get("weapon"), sword)


class TestHubScreen(unittest.TestCase):
    def _gui(self):
        pygame.display.init()
        pygame.display.set_mode((1200, 800))
        from ui.gui import GameGUI
        engine = GameEngine(llm_provider="heuristic",
                            enable_npc_processes=False)
        engine.start_game()
        return GameGUI(engine)

    def _key(self, code):
        return pygame.event.Event(pygame.KEYDOWN, key=code, unicode="",
                                  mod=0)

    def test_c_opens_hub_and_esc_closes(self):
        gui = self._gui()
        gui.mode = "play"
        gui.input_handler.handle_event(self._key(pygame.K_c))
        self.assertEqual(gui.mode, "player")
        gui.input_handler.handle_event(self._key(pygame.K_ESCAPE))
        self.assertEqual(gui.mode, "play")
        gui.engine.end_game()

    def test_every_tab_draws_headless(self):
        from ui.player_screen import TABS
        gui = self._gui()
        gui.show_player_screen()
        for i in range(len(TABS)):
            gui.player_screen.tab = i
            gui.player_screen.draw(gui.screen)   # must not raise
        gui.engine.end_game()

    def test_bracket_switches_tabs(self):
        gui = self._gui()
        gui.show_player_screen()
        start = gui.player_screen.tab
        gui.input_handler.handle_event(self._key(pygame.K_RIGHTBRACKET))
        self.assertNotEqual(gui.player_screen.tab, start)
        gui.engine.end_game()


if __name__ == "__main__":
    unittest.main()
