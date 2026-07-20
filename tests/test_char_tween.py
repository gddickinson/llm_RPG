"""Continuous tile-to-tile motion (George: NPC movement was jerky stop/start).

An NPC's tile-slide STRETCHES to fill the gap since its last step so ambient
motion glides continuously; the player keeps a crisp fixed step; the stride
cycles with ground speed. Covered as pure helpers + through `update_anim`.
"""

import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
import pygame                                            # noqa: E402
pygame.init()

from ui import char_tween as ct                          # noqa: E402
from ui.body_renderer import update_anim, TWEEN_DUR, NPC_TWEEN_MAX  # noqa: E402


class _Char:
    def __init__(self, cid, pos):
        self.id, self.position, self.metadata = cid, pos, {}

    def is_alive(self):
        return True


def _stand(c, frames):
    for _ in range(frames):
        update_anim(c, 1 / 30.0)


class TestStartSlide(unittest.TestCase):
    def test_npc_slide_fills_the_gap(self):
        anim = {"since_move": 0.6}
        ct.start_slide(anim, (5, 5), (6, 5), is_player=False)
        self.assertAlmostEqual(anim["tween_dur"], 0.6, places=3)
        self.assertEqual(anim["tween_from"], (-1, 0))
        self.assertEqual(anim["since_move"], 0.0)

    def test_npc_slide_is_capped(self):
        anim = {"since_move": 4.0}          # a lone step after a long stand
        ct.start_slide(anim, (1, 1), (2, 1), is_player=False)
        self.assertAlmostEqual(anim["tween_dur"], NPC_TWEEN_MAX, places=6)

    def test_player_slide_is_always_crisp(self):
        anim = {"since_move": 3.0}
        ct.start_slide(anim, (0, 0), (1, 0), is_player=True)
        self.assertAlmostEqual(anim["tween_dur"], TWEEN_DUR, places=6)

    def test_a_short_gap_never_dips_below_the_base(self):
        anim = {"since_move": 0.02}         # a fast burst of steps
        ct.start_slide(anim, (0, 0), (1, 0), is_player=False)
        self.assertGreaterEqual(anim["tween_dur"], TWEEN_DUR)


class TestAdvanceSlide(unittest.TestCase):
    def test_stride_advances_with_ground_speed(self):
        # a longer slide advances the stride more slowly per frame (so the legs
        # cycle at the glide's pace, not a fixed clock)
        fast = {"tween_dur": 0.2, "tween_t": 0.2}
        slow = {"tween_dur": 0.8, "tween_t": 0.8}
        ct.advance_slide(fast, 1 / 30.0)
        ct.advance_slide(slow, 1 / 30.0)
        self.assertGreater(fast["move_phase"], slow["move_phase"])

    def test_one_tile_is_about_one_step(self):
        # advancing a full tween's worth of time crosses STRIDE_PER_TILE cycles
        anim = {"tween_dur": 0.6, "tween_t": 0.6}
        for _ in range(18):                 # 18/30 = 0.6s ≈ one tile
            ct.advance_slide(anim, 1 / 30.0)
        self.assertAlmostEqual(anim["move_phase"], ct.STRIDE_PER_TILE, delta=0.06)


class TestThroughUpdateAnim(unittest.TestCase):
    def test_idle_npc_step_glides(self):
        c = _Char("npc", (5, 5))
        update_anim(c, 1 / 30.0)
        _stand(c, 20)                       # ~0.66s idle → gap accrues
        c.position = (6, 5)
        update_anim(c, 1 / 30.0, is_player=False)
        dur = c.metadata["_anim"]["tween_dur"]
        self.assertGreater(dur, TWEEN_DUR, "an NPC's slide stretches to glide")
        self.assertLessEqual(dur, NPC_TWEEN_MAX)

    def test_player_step_stays_crisp(self):
        p = _Char("hero", (3, 3))
        update_anim(p, 1 / 30.0)
        _stand(p, 40)
        p.position = (4, 3)
        update_anim(p, 1 / 30.0, is_player=True)
        self.assertAlmostEqual(p.metadata["_anim"]["tween_dur"], TWEEN_DUR,
                               places=6)

    def test_iso_tween_pos_uses_the_char_duration(self):
        from ui.iso_actors import tween_world_pos
        c = _Char("npc2", (10, 10))
        update_anim(c, 1 / 30.0)
        _stand(c, 20)
        c.position = (11, 10)
        update_anim(c, 1 / 30.0, is_player=False)   # a fresh, near-full slide
        fx, fy = tween_world_pos(c, 11, 10)
        self.assertTrue(10.0 <= fx < 11.01, "mid-slide, between the tiles")
        self.assertAlmostEqual(fy, 10.0, places=3)


if __name__ == "__main__":
    unittest.main()
