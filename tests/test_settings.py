"""Settings overlay (PUX.4a) + the ESC quit-confirmation."""

import os as _os
import tempfile as _tempfile
import types
import unittest

_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_lib_"))

from engine import settings                          # noqa: E402


def _player():
    return types.SimpleNamespace(metadata={})


class TestSettingsModel(unittest.TestCase):
    def test_defaults(self):
        p = _player()
        self.assertEqual(settings.get_setting(p, "zoom"), 48)
        self.assertEqual(settings.get_setting(p, "hints"), "on")
        self.assertTrue(settings.enabled(p, "minimap"))

    def test_set_and_persist_in_metadata(self):
        p = _player()
        settings.set_setting(p, "sound", "off")
        self.assertEqual(p.metadata["settings"]["sound"], "off")
        self.assertFalse(settings.enabled(p, "sound"))

    def test_cycle_wraps(self):
        p = _player()
        seen = [settings.get_setting(p, "zoom")]
        for _ in range(3):
            seen.append(settings.cycle_setting(p, "zoom"))
        self.assertEqual(seen, [48, 64, 24, 32])   # wraps round

    def test_cycle_backwards(self):
        p = _player()
        self.assertEqual(settings.cycle_setting(p, "hints", -1), "off")

    def test_log_detail_shares_the_event_filter_store(self):
        # log_detail must write log_verbosity, not a private key, so the
        # event filter and the settings overlay stay in sync.
        p = _player()
        settings.set_setting(p, "log_detail", "verbose")
        self.assertEqual(p.metadata["log_verbosity"], "verbose")
        self.assertNotIn("log_detail",
                         p.metadata.get("settings", {}))


class TestSettingsAndQuitInGui(unittest.TestCase):
    def _gui(self):
        import pygame
        pygame.display.init()
        pygame.display.set_mode((1280, 800))
        from engine.game_engine import GameEngine
        from ui.gui import GameGUI
        engine = GameEngine(llm_provider="heuristic",
                            enable_npc_processes=False)
        engine.start_game()
        return GameGUI(engine)

    def _key(self, code):
        import pygame
        return pygame.event.Event(pygame.KEYDOWN, key=code, unicode="")

    def test_settings_overlay_opens_and_zoom_applies_live(self):
        import pygame
        gui = self._gui()
        gui.show_settings()
        self.assertEqual(gui.mode, "settings")
        gui.settings_panel.cursor = 4          # the zoom row
        gui.settings_panel.handle_key(self._key(pygame.K_RIGHT))
        self.assertEqual(gui.renderer.tile_size,
                         settings.get_setting(gui.engine.player, "zoom"))
        gui.settings_panel.handle_key(self._key(pygame.K_ESCAPE))
        self.assertEqual(gui.mode, "play")
        gui.engine.end_game()

    def test_escape_asks_before_quitting(self):
        import pygame
        gui = self._gui()
        gui.mode = "play"
        gui.running = True                     # the loop is live
        gui.input_handler.handle_event(self._key(pygame.K_ESCAPE))
        self.assertEqual(gui.mode, "confirm_quit",
                         "ESC must not quit outright")
        self.assertTrue(gui.running, "still running")
        # 'N' backs out
        gui.input_handler.handle_event(self._key(pygame.K_n))
        self.assertEqual(gui.mode, "play")
        self.assertTrue(gui.running)
        # ESC then 'Y' actually quits
        gui.input_handler.handle_event(self._key(pygame.K_ESCAPE))
        gui.input_handler.handle_event(self._key(pygame.K_y))
        self.assertFalse(gui.running, "confirmed quit stops the loop")


if __name__ == "__main__":
    unittest.main()
