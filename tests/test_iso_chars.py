"""P41.5 — baked 3D character figures for the iso world (headless)."""

import os as _os
_os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
_os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import types
import unittest

import pygame

from ui import iso_chars as ic


def _char(cls="warrior"):
    return types.SimpleNamespace(
        character_class=types.SimpleNamespace(value=cls),
        metadata={}, hair="hair_brown", position=(5, 5))


def _painted(spr):
    w, h = spr.get_size()
    return sum(1 for x in range(0, w, 3) for y in range(0, h, 3)
               if spr.get_at((x, y))[3] > 0)


class TestCharSprite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    def test_a_figure_bakes(self):
        spr = ic.char_sprite(_char(), 48, facing=2)
        self.assertEqual(spr.get_size(), (48, 48))
        self.assertGreater(_painted(spr), 20)

    def test_cached_by_look_and_facing(self):
        c = _char("warrior")
        self.assertIs(ic.char_sprite(c, 48, 2), ic.char_sprite(c, 48, 2))

    def test_classes_tint_apart(self):
        w = ic._tint(_char("warrior"))
        m = ic._tint(_char("wizard"))
        self.assertNotEqual(w, m, "a warrior and a wizard should differ")

    def test_facing_turns_the_figure(self):
        c = _char()
        south = ic.char_sprite(c, 56, 2)
        east = ic.char_sprite(c, 56, 1)
        diff = any(south.get_at((x, y)) != east.get_at((x, y))
                   for x in range(0, 56, 4) for y in range(0, 56, 4))
        self.assertTrue(diff, "the facing nub should move")

    def test_facing_of_returns_a_direction(self):
        self.assertIn(ic.facing_of(_char()), (0, 1, 2, 3))


class TestInScene(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        import tempfile
        _os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                               tempfile.mkdtemp(prefix="llmrpg_isoc_"))
        from engine.game_engine import GameEngine
        cls.engine = GameEngine(llm_provider="heuristic",
                                enable_npc_processes=False)
        cls.engine.start_game()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.engine.end_game()
        except Exception:
            pass

    def test_visible_chars_include_the_hero(self):
        from ui.iso_render import _visible_chars
        chars = _visible_chars(self.engine)
        self.assertIn(self.engine.player, chars)
        self.assertGreater(len(chars), 1, "some NPCs are visible too")

    def test_iso_frame_with_chars_paints(self):
        from ui import iso_render
        surf = pygame.Surface((640, 480))
        surf.fill((0, 0, 0))
        iso_render.render_iso(surf, self.engine,
                              pygame.Rect(0, 0, 640, 480), 48)
        painted = sum(1 for x in range(0, 640, 12) for y in range(0, 480, 12)
                      if surf.get_at((x, y))[:3] != (0, 0, 0))
        self.assertGreater(painted, 40)


if __name__ == "__main__":
    unittest.main()
