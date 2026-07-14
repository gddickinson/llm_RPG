"""P34.2 — facial expression, blink, and emote bubbles."""

import os as _os
import tempfile as _tempfile
_os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
_os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_cf_"))

import unittest

from ui import char_face as cf


class TestExpressions(unittest.TestCase):
    def test_table_well_formed(self):
        for name, s in cf.EXPRESSIONS.items():
            self.assertIn("brow", s)
            self.assertIn("mouth", s)
            self.assertIn(s["eyes"], ("dot", "arch", "squint", "wide", "x"), name)

    def test_expr_for_reads_metadata_else_neutral(self):
        class C:
            metadata = {"_expr": "angry"}
        self.assertEqual(cf.expr_for(C()), "angry")

        class D:
            metadata = {}
        self.assertEqual(cf.expr_for(D()), "neutral")
        self.assertEqual(cf.expr_for(D()), cf.DEFAULT_EXPR)

    def test_emote_expr_mapping(self):
        self.assertEqual(cf.EMOTE_EXPR["hurt"], "hurt")
        self.assertEqual(cf.EMOTE_EXPR["cheer"], "happy")


class TestBlink(unittest.TestCase):
    def test_blink_cycle(self):
        anim = {}
        # first call inits and is open
        self.assertFalse(cf.blink_step(anim, 1 / 30, 3))
        # run the clock down — eventually it shuts, then reopens
        closed = opened = False
        for _ in range(600):
            b = cf.blink_step(anim, 1 / 30, 3)
            closed = closed or b
            if closed and not b:
                opened = True
        self.assertTrue(closed and opened)

    def test_seed_changes_the_interval(self):
        a1, a2 = {}, {}
        cf.blink_step(a1, 0.0, 1)
        cf.blink_step(a2, 0.0, 20)
        self.assertNotEqual(a1["blink_t"], a2["blink_t"])


class TestRenderSmoke(unittest.TestCase):
    def test_faces_and_bubbles_draw(self):
        import pygame
        pygame.init()
        pygame.display.set_mode((64, 64))
        from ui import body_parts as bp
        surf = pygame.Surface((64, 64))
        for name in cf.EXPRESSIONS:
            for prof in (0, 1, -1):
                for blink in (False, True):
                    bp.draw_face(surf, 32, 20, 9, name, prof, blink)
        for kind in cf.BUBBLES:
            bp.draw_bubble(surf, 32, 30, kind, 9)     # must not raise


if __name__ == "__main__":
    unittest.main()
