"""P34.10 — the expanded acrobatics / daily-life clip library.

Every new clip must register, keep the skeleton complete & finite across its arc,
be flagged one-shot vs held correctly, and a few must express their motion.
"""

import os as _os
import math
import tempfile as _tempfile
_os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_ccm_"))

import unittest

from ui import char_clips as cc
from ui.char_pose import build_pose

BUILD = {"shoulder": 1.0, "hip": 1.0, "head": 1.0, "girth": 1.0, "h": 1.0}
JOINTS = ["l_hip", "r_hip", "chest", "l_knee", "r_knee", "l_foot", "r_foot",
          "l_sh", "r_sh", "neck", "head", "l_elbow", "l_hand", "r_elbow",
          "r_hand"]
NEW = ["flip", "somersault", "cartwheel", "roll", "twirl", "lunge", "crawl",
       "crouch", "eat", "drink", "rest", "lie", "stretch", "yawn", "clap",
       "laugh", "shrug", "ponder", "salute", "beckon", "facepalm"]
H = 80


def _rest(facing=(1, 0)):
    return build_pose(100, 300, H, 0.0, 0.0, False, 0.0, facing, BUILD)


class TestRegistration(unittest.TestCase):
    def test_all_registered(self):
        for a in NEW:
            self.assertIn(a, cc.ACTIONS, a)
            self.assertIn(a, cc._CLIPS, a)

    def test_oneshots_have_a_duration(self):
        for a in ("flip", "lunge", "drink", "stretch", "salute"):
            self.assertTrue(cc.is_one_shot(a), a)
            self.assertIsInstance(cc.duration(a), float)

    def test_held_stances_are_loops(self):
        for a in ("crawl", "crouch", "rest", "lie"):
            self.assertFalse(cc.is_one_shot(a), a)
            self.assertIsNone(cc.duration(a), a)


class TestSkeletonIntegrity(unittest.TestCase):
    def test_joints_complete_and_finite_across_the_arc(self):
        for a in NEW:
            for ph in (0.0, 0.2, 0.5, 0.8, 1.0):
                out = cc.apply(a, _rest(), ph, H, (1, 0))
                for k in JOINTS:
                    self.assertIn(k, out, f"{a}@{ph} missing {k}")
                    x, y = out[k]
                    self.assertTrue(math.isfinite(x) and math.isfinite(y),
                                    f"{a}@{ph} {k}=({x},{y})")

    def test_works_facing_both_ways(self):
        for facing in ((1, 0), (-1, 0)):
            for a in ("lunge", "roll", "flip", "crawl"):
                out = cc.apply(a, _rest(facing), 0.5, H, facing)
                self.assertEqual(len(out.get("head", ())), 2)


class TestExpression(unittest.TestCase):
    def test_flip_inverts_at_apex_then_lands_upright(self):
        mid = cc.apply("flip", _rest(), 0.5, H, (1, 0))
        self.assertGreater(mid["head"][1], mid["l_hip"][1])   # head below hips
        end = cc.apply("flip", _rest(), 1.0, H, (1, 0))
        self.assertLess(end["head"][1], end["l_hip"][1])      # upright again
        self.assertAlmostEqual(end["l_foot"][1], _rest()["l_foot"][1],
                               delta=H * 0.12)                # feet back to ground

    def test_lie_is_horizontal(self):
        out = cc.apply("lie", _rest(), 0.0, H, (1, 0))
        self.assertLess(abs(out["head"][1] - out["l_hip"][1]), H * 0.3)

    def test_lunge_drives_the_front_foot_forward(self):
        out = cc.apply("lunge", _rest(), 0.5, H, (1, 0))
        self.assertGreater(out["r_foot"][0], _rest()["r_foot"][0] + H * 0.1)

    def test_crouch_lowers_the_torso(self):
        out = cc.apply("crouch", _rest(), 0.0, H, (1, 0))
        self.assertGreater(out["chest"][1], _rest()["chest"][1])   # y down = lower

    def test_stretch_lifts_the_hands(self):
        out = cc.apply("stretch", _rest(), 0.5, H, (1, 0))
        self.assertLess(out["r_hand"][1], _rest()["r_hand"][1] - H * 0.1)

    def test_arc_oneshots_return_to_rest_at_the_ends(self):
        # clips built on _arc are neutral at t=0 and t=1
        for a in ("stretch", "shrug", "ponder", "drink", "facepalm", "yawn"):
            for t in (0.0, 1.0):
                out = cc.apply(a, _rest(), t, H, (1, 0))
                for k in ("chest", "l_hip"):
                    self.assertAlmostEqual(out[k][0], _rest()[k][0], delta=1.0,
                                           msg=f"{a}@{t} {k}")
                    self.assertAlmostEqual(out[k][1], _rest()[k][1], delta=1.0,
                                           msg=f"{a}@{t} {k}")


if __name__ == "__main__":
    unittest.main()
