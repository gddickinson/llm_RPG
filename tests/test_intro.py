"""The cold-open prologue (GAP.7): a class/world-aware framing shown once
on a new game, dismissed by any key."""

import unittest

import pygame

from engine.game_engine import GameEngine
from engine import intro


class TestIntroText(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False)
        self.engine.start_game()

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_intro_text_names_the_hero(self):
        title, lines = intro.intro_text(self.engine)
        self.assertIn(self.engine.player.name, title)
        self.assertTrue(lines)
        blob = " ".join(lines)
        self.assertIn(self.engine.player.name, blob)

    def test_shows_once_then_marked_seen(self):
        self.assertTrue(intro.should_show(self.engine))
        intro.mark_seen(self.engine)
        self.assertFalse(intro.should_show(self.engine))

    def test_seen_flag_persists_through_save(self):
        import tempfile
        intro.mark_seen(self.engine)
        path = tempfile.mkdtemp() + "/s.json"
        self.engine.save_game(path)
        eng2 = GameEngine(llm_provider="heuristic",
                          enable_npc_processes=False)
        eng2.load_game(path)
        self.assertFalse(intro.should_show(eng2))
        try:
            eng2.end_game()
        except Exception:
            pass


class TestIntroScreen(unittest.TestCase):
    def _gui(self):
        pygame.display.init()
        pygame.display.set_mode((1100, 760))
        from ui.gui import GameGUI
        engine = GameEngine(llm_provider="heuristic",
                            enable_npc_processes=False)
        engine.start_game()
        return GameGUI(engine)

    def test_draw_and_dismiss(self):
        gui = self._gui()
        gui.show_intro()
        self.assertEqual(gui.mode, "intro")
        from ui.intro_screen import draw_intro
        draw_intro(gui)                       # must not raise
        # any key begins the game
        ev = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE,
                                unicode=" ", mod=0)
        gui.input_handler.handle_event(ev)
        self.assertEqual(gui.mode, "play")
        self.assertFalse(intro.should_show(gui.engine))
        gui.engine.end_game()


if __name__ == "__main__":
    unittest.main()
