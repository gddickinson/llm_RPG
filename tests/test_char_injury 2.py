"""P34.17 — injury & state animation modifiers."""

import os as _os
import math
import tempfile as _tempfile
_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_inj_"))

import unittest

from ui import char_injury as ci


class _Char:
    def __init__(self, meta):
        self.metadata = meta


class TestInjuryState(unittest.TestCase):
    def test_healthy(self):
        st = ci.injury_state(_Char({}))
        self.assertFalse(st["down"])
        self.assertEqual(st["limp"], 0)
        self.assertIsNone(st["arm"])

    def test_leg_wound_limps(self):
        st = ci.injury_state(_Char({"wounds": {"legs": 3}}))
        self.assertGreater(st["limp"], 0)
        self.assertFalse(st["down"])

    def test_arm_wound_picks_the_worse_side(self):
        self.assertEqual(ci.injury_state(_Char({"wounds": {"right_arm": 2}}))["arm"],
                         "r")
        self.assertEqual(ci.injury_state(_Char({"wounds": {"left_arm": 2}}))["arm"],
                         "l")

    def test_dying_and_unconscious_are_down(self):
        self.assertTrue(ci.injury_state(_Char({"dying": 2}))["down"])
        self.assertTrue(ci.injury_state(_Char({"unconscious": True}))["down"])
        self.assertTrue(ci.injury_state(_Char({"ko": True}))["down"])


class TestApply(unittest.TestCase):
    def _pose(self):
        return {"chest": (50, 20), "l_hip": (45, 30), "r_hip": (55, 30),
                "neck": (50, 15), "head": (50, 10), "l_sh": (44, 18),
                "r_sh": (56, 18), "l_elbow": (43, 25), "r_elbow": (57, 25),
                "l_hand": (43, 32), "r_hand": (57, 32), "l_foot": (45, 40),
                "r_foot": (55, 40), "l_knee": (45, 35), "r_knee": (55, 35)}

    def test_limp_dips_the_body(self):
        pose = self._pose()
        y0 = pose["chest"][1]
        ci.apply_limp(pose, math.pi / 2, 80, 1.0)     # sin=1 → max hitch
        self.assertGreater(pose["chest"][1], y0)      # torso dips down

    def test_limp_zero_is_a_noop(self):
        pose = self._pose()
        before = dict(pose)
        ci.apply_limp(pose, 1.0, 80, 0.0)
        self.assertEqual(pose["chest"], before["chest"])

    def test_injured_arm_hangs_under_the_shoulder(self):
        pose = self._pose()
        ci.apply_arm(pose, "r", 80)
        self.assertAlmostEqual(pose["r_hand"][0], pose["r_sh"][0], delta=1)
        self.assertGreater(pose["r_hand"][1], pose["r_sh"][1])   # hangs down


if __name__ == "__main__":
    unittest.main()
