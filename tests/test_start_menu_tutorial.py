"""Audit fix (A-disc): Tutorial Island is reachable from the GUI menu, and
left-click-to-target is documented in the controls help.

Tutorial Island used to be reachable ONLY via the `--tutorial` CLI flag; a
new-player who launched the GUI never saw it. It now sits in the New Game
menu and returns a `start:"tutorial"` choice (which `main.py` routes to the
`start_tutorial` engine flag).
"""

import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import unittest

import pygame
pygame.init()
pygame.display.set_mode((1024, 700))

from ui.start_menu import StartMenu, NEW_GAME_OPTIONS
from ui import controls


class TestTutorialMenuOption(unittest.TestCase):
    def test_tutorial_island_is_in_the_menu(self):
        codes = [c for _label, c in NEW_GAME_OPTIONS]
        self.assertIn("tutorial", codes,
                      "Tutorial Island should be a New Game option")

    def test_selecting_it_returns_a_tutorial_start(self):
        m = StartMenu()
        m.state = "new_game"
        m.selected = [c for _l, c in NEW_GAME_OPTIONS].index("tutorial")
        choice = m._newgame_key(pygame.K_RETURN)
        self.assertIsNotNone(choice, "Enter on Tutorial Island starts a game")
        self.assertEqual(choice["action"], "new")
        self.assertEqual(choice["start"], "tutorial")
        self.assertIsNotNone(choice.get("spec"), "a hero is made for it")


class TestLeftClickTargetDocumented(unittest.TestCase):
    def test_left_click_target_is_in_the_fight_help(self):
        keys = controls.documented_keys()
        self.assertIn("L-CLICK", keys,
                      "left-click-to-target should be documented")

    def test_it_lives_in_the_fight_section(self):
        fight = next((entries for title, entries in controls.CONTROLS
                      if title == "FIGHT"), [])
        fight_keys = [k for k, _desc in fight]
        self.assertIn("L-CLICK", fight_keys)


if __name__ == "__main__":
    unittest.main()
