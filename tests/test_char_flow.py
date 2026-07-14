"""P34.5 — hair / cloak / weapon-trail flow: the verlet chain + trail + draw."""

import os as _os
import math
import tempfile as _tempfile
_os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_flow_"))

import unittest
import pygame
pygame.init()

from ui import char_flow as cf


class TestChain(unittest.TestCase):
    def test_init_hangs_below_the_root(self):
        nodes = cf.init_chain(5, 5, 3, 10)
        self.assertEqual(len(nodes), 3)
        self.assertTrue(all(n[1] > 5 for n in nodes))       # each below the root

    def test_segments_hold_their_length(self):
        nodes = cf.init_chain(0, 0, 3, 10)
        for _ in range(30):
            cf.step_chain(nodes, 0, 0, 10, 0.5, 0.86, 0.0)
        prev = (0.0, 0.0)
        for n in nodes:
            d = math.hypot(n[0] - prev[0], n[1] - prev[1])
            self.assertAlmostEqual(d, 10, delta=0.6)
            prev = (n[0], n[1])

    def test_chain_trails_a_moving_root(self):
        nodes = cf.init_chain(0, 0, 3, 10)
        for i in range(15):
            cf.step_chain(nodes, i * 4, 0, 10, 0.5, 0.86, 0.0)
        # the tip lags well behind the root that has slid to x=56
        self.assertLess(nodes[-1][0], 56 - 5)

    def test_settles_when_still(self):
        nodes = cf.init_chain(0, 0, 3, 10)
        for _ in range(200):
            cf.step_chain(nodes, 0, 0, 10, 0.5, 0.86, 0.0)
        # velocity (pos - prevpos) has damped to ~0
        self.assertLess(abs(nodes[-1][0] - nodes[-1][2]), 0.2)


class TestTrail(unittest.TestCase):
    def test_caps_at_max(self):
        t = []
        for i in range(20):
            cf.push_trail(t, i, i)
        self.assertEqual(len(t), cf.TRAIL_MAX)
        self.assertEqual(t[-1], [19, 19])                   # newest kept


class TestDrawSmoke(unittest.TestCase):
    def _pose(self):
        return {"neck": (50, 40), "head": (50, 30), "head_r": 8,
                "l_sh": (44, 44), "r_sh": (56, 44), "r_hand": (60, 60),
                "fdir": 1}

    def test_draw_back_and_front_do_not_crash(self):
        surf = pygame.Surface((100, 160), pygame.SRCALPHA)
        anim = {"clock": 0.3, "_sec": {}}
        pose = self._pose()
        # cloak class + hair
        cf.draw_back(surf, None, anim, pose, 0, 100, 48, 80,
                     (60, 40, 26), (40, 30, 60))
        # a swing builds a trail; drawing it must not raise
        for _ in range(4):
            cf.draw_front(surf, anim, pose, 0, 100, 48, 0.2, "sword")
        cf.draw_front(surf, anim, pose, 0, 100, 48, 0.0, "sword")   # fade
        self.assertIn("hair", anim["_sec"])
        self.assertIn("cloak", anim["_sec"])

    def test_no_cloak_when_color_none(self):
        surf = pygame.Surface((100, 160), pygame.SRCALPHA)
        anim = {"clock": 0.0, "_sec": {}}
        cf.draw_back(surf, None, anim, self._pose(), 0, 100, 48, 80,
                     (60, 40, 26), None)
        self.assertNotIn("cloak", anim["_sec"])
        self.assertIn("hair", anim["_sec"])

    def test_cloak_classes_listed(self):
        for k in ("wizard", "rogue", "cleric"):
            self.assertIn(k, cf.CLOAK_CLASSES)


if __name__ == "__main__":
    unittest.main()
