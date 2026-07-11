"""Controls help (PUX.3): the reference is complete, fits two columns,
and the overlay renders + dismisses."""

import os as _os
import tempfile as _tempfile
import unittest

_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_lib_"))

from ui import controls                              # noqa: E402


class TestControlsData(unittest.TestCase):
    def test_covers_the_previously_undocumented_keys(self):
        keys = controls.documented_keys()
        # the audit gaps — skill actions, pray, carry, pet, targeting,
        # force-door, log detail, the law menu — are now all in.
        for k in ("SHIFT + T", "SHIFT + I", "SHIFT + B", "SHIFT + H",
                  "SHIFT + P", "SHIFT + G", "SHIFT + Z", "[ / ]",
                  "SHIFT + TAB", "SHIFT + L", "1 – 5", "SHIFT + V"):
            self.assertIn(k, keys, f"{k} should be documented")

    def test_covers_the_core_verbs(self):
        keys = controls.documented_keys()
        for k in ("WASD / Arrows", "SPACE / F", "T", "B", "X", "I",
                  "TAB", "F1 or ?", "ESC"):
            self.assertIn(k, keys)

    def test_two_balanced_columns_that_fit(self):
        left, right = controls.help_columns()
        self.assertTrue(left and right, "both columns have content")
        # each must fit the ~30-row overlay (the old single list clipped)
        self.assertLessEqual(len(left), 32)
        self.assertLessEqual(len(right), 32)
        # roughly balanced
        self.assertLessEqual(abs(len(left) - len(right)), 12)

    def test_section_headers_are_present(self):
        left, right = controls.help_columns()
        joined = left + right
        for section in ("MOVE & EXPLORE", "FIGHT", "PEOPLE & WORLD",
                        "PANELS & JOURNALS", "SYSTEM"):
            self.assertIn(section, joined)

    def test_no_entry_line_overflows_a_column(self):
        # 14px monospace in a ~434px column fits ~50 chars
        for line in sum(controls.help_columns(), []):
            self.assertLessEqual(len(line), 50, line)


class TestHelpOverlay(unittest.TestCase):
    def test_show_help_opens_and_a_key_dismisses(self):
        import pygame
        pygame.display.init()
        pygame.display.set_mode((1024, 700))
        from engine.game_engine import GameEngine
        from ui.gui import GameGUI
        engine = GameEngine(llm_provider="heuristic",
                            enable_npc_processes=False)
        engine.start_game()
        gui = GameGUI(engine)
        gui.show_help()
        self.assertEqual(gui.mode, "help")
        self.assertTrue(gui.help_columns[0], "columns populated")
        # the overlay draws without crashing
        gui.hud.draw_help_overlay(
            pygame.Surface((1024, 700)),
            pygame.Rect(0, 0, 1024, 700), "Controls", gui.help_columns)
        # any key returns to play
        ev = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_x)
        gui.input_handler.handle_event(ev)
        self.assertEqual(gui.mode, "play")
        engine.end_game()


if __name__ == "__main__":
    unittest.main()
