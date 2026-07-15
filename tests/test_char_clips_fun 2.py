"""P34.13 — comedy & dance clips: registration, integrity, and the emote key."""

import os as _os
import math
import tempfile as _tempfile
_os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_fun_"))

import unittest

from ui import char_clips as cc
from ui.char_pose import build_pose

FUN = ["jig", "kick", "moonwalk", "robot", "flex", "taunt", "wiggle", "disco",
       "airguitar", "facepalm2"]
BUILD = {"shoulder": 1.0, "hip": 1.0, "head": 1.0, "girth": 1.0, "h": 1.0}
JOINTS = ["l_hip", "r_hip", "chest", "l_knee", "r_knee", "l_foot", "r_foot",
          "l_sh", "r_sh", "neck", "head", "l_elbow", "l_hand", "r_elbow",
          "r_hand"]


def _rest():
    return build_pose(100, 300, 80, 0.0, 0.0, False, 0.0, (1, 0), BUILD)


class TestComedyClips(unittest.TestCase):
    def test_all_registered_as_oneshots(self):
        for a in FUN:
            self.assertIn(a, cc._CLIPS, a)
            self.assertTrue(cc.is_one_shot(a), a)
            self.assertIsInstance(cc.duration(a), float)

    def test_joints_complete_and_finite(self):
        for a in FUN:
            for ph in (0.0, 0.25, 0.5, 0.75, 1.0):
                out = cc.apply(a, _rest(), ph, 80, (1, 0))
                for k in JOINTS:
                    self.assertIn(k, out, f"{a}@{ph} missing {k}")
                    x, y = out[k]
                    self.assertTrue(math.isfinite(x) and math.isfinite(y),
                                    f"{a}@{ph} {k}")

    def test_flex_raises_both_fists(self):
        out = cc.apply("flex", _rest(), 0.5, 80, (1, 0))
        rest = _rest()
        self.assertLess(out["l_hand"][1], rest["l_hand"][1])   # hands up
        self.assertLess(out["r_hand"][1], rest["r_hand"][1])

    def test_kick_flings_a_foot_up(self):
        # somewhere in the clip a foot rises well above its rest height
        highest = min(cc.apply("kick", _rest(), ph, 80, (1, 0))["r_foot"][1]
                      for ph in (0.1, 0.2, 0.3))
        self.assertLess(highest, _rest()["r_foot"][1] - 80 * 0.05)


class TestEmoteKey(unittest.TestCase):
    def test_perform_emote_sets_a_comedy_move(self):
        from ui import input_actions as ia

        class _Mem:
            def add_event(self, m):
                pass

        class _P:
            def __init__(self):
                self.metadata = {}

        class _E:
            def __init__(self):
                self.player = _P()
                self.memory_manager = _Mem()

        class _H:
            def __init__(self):
                self.engine = _E()

        h = _H()
        ia.perform_emote(h)
        self.assertIn(h.engine.player.metadata.get("_emote"), ia._EMOTES)


if __name__ == "__main__":
    unittest.main()
