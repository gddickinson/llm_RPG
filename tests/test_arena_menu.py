"""Combat Arena start-menu item — the colosseum reachable from the title
screen (George): the matchups list, keyboard navigation, and the pick result
main.py stages."""

import os as _os
import unittest

_os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
_os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame                                            # noqa: E402
pygame.init()
pygame.display.set_mode((1024, 700))

from ui.start_menu import StartMenu, TITLE_OPTIONS       # noqa: E402
from engine.colosseum import list_matchups               # noqa: E402


class TestListMatchups(unittest.TestCase):
    def test_matchups_load_engine_free(self):
        ms = list_matchups()
        self.assertTrue(ms, "matchups load from data/colosseum.json")
        for mid, name, desc in ms:            # (id, name, desc) triples
            self.assertTrue(mid and name)


class TestArenaMenu(unittest.TestCase):
    def setUp(self):
        self.m = StartMenu()
        self.m._refresh_matchups()
        self.m.state = "arena_menu"

    def test_combat_arena_is_a_title_option(self):
        self.assertIn("arena", [code for _, code in TITLE_OPTIONS])

    def test_title_pick_opens_the_arena_menu(self):
        self.m.state = "title"
        self.m.selected = [c for _, c in TITLE_OPTIONS].index("arena")
        self.assertIsNone(self.m._pick_title())
        self.assertEqual(self.m.state, "arena_menu")
        self.assertTrue(self.m.matchups)

    def test_renders_without_crashing(self):
        self.m._render_arena_list()

    def test_navigation_stays_in_bounds(self):
        n = len(self.m.matchups)
        self.m.selected = 0
        for key in (pygame.K_DOWN, pygame.K_DOWN, pygame.K_UP, pygame.K_DOWN):
            self.m._arena_key(key)
            self.assertTrue(0 <= self.m.selected < n)

    def test_enter_returns_an_arena_pick(self):
        self.m.selected = 2
        out = self.m._arena_key(pygame.K_RETURN)
        self.assertEqual(out["action"], "arena")
        self.assertEqual(out["matchup"], self.m.matchups[2][0])
        self.assertIsNotNone(out["spec"], "a default hero to spectate with")
        self.assertEqual(out["start"], "default")

    def test_esc_returns_to_the_title(self):
        self.m._arena_key(pygame.K_ESCAPE)
        self.assertEqual(self.m.state, "title")


if __name__ == "__main__":
    unittest.main()
