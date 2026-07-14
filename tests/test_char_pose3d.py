"""P34.14 groundwork — the 3D-body-coordinate pose (continuous facing)."""

import os as _os
import math
import tempfile as _tempfile
_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_p3_"))

import unittest

from ui import char_pose3d as p3

JOINTS = ["l_hip", "r_hip", "chest", "l_knee", "r_knee", "l_foot", "r_foot",
          "l_sh", "r_sh", "neck", "head", "l_elbow", "l_hand", "r_elbow",
          "r_hand"]


def _sep(pose, a, b):
    return abs(pose[a][0] - pose[b][0])


class TestProjection(unittest.TestCase):
    def test_all_joints_finite_at_every_facing(self):
        for deg in range(0, 360, 30):
            pose = p3.pose3d(60, 120, 80, 1.0, deg)
            for k in JOINTS:
                x, y = pose[k]
                self.assertTrue(math.isfinite(x) and math.isfinite(y),
                                f"{k}@{deg}")

    def test_profile_is_narrower_than_front(self):
        front = p3.pose3d(60, 120, 80, 0.0, 0)
        prof = p3.pose3d(60, 120, 80, 0.0, 90)
        self.assertGreater(_sep(front, "l_sh", "r_sh"),
                           _sep(prof, "l_sh", "r_sh") + 5)

    def test_face_shows_front_hides_back(self):
        self.assertTrue(p3.pose3d(60, 120, 80, 0, 0)["face_visible"])
        self.assertFalse(p3.pose3d(60, 120, 80, 0, 180)["face_visible"])

    def test_profile_sign_flips_with_side(self):
        self.assertEqual(p3.pose3d(60, 120, 80, 0, 90)["profile"], 1)
        self.assertEqual(p3.pose3d(60, 120, 80, 0, 270)["profile"], -1)
        self.assertEqual(p3.pose3d(60, 120, 80, 0, 0)["profile"], 0)


class TestWalkProjection(unittest.TestCase):
    def test_front_walk_does_not_stride_horizontally(self):
        # at the front, the fore-aft stride shows as a LIFT, not x separation
        a = p3.pose3d(60, 120, 80, 0.0, 0)
        b = p3.pose3d(60, 120, 80, math.pi / 2, 0)
        self.assertAlmostEqual(_sep(a, "l_foot", "r_foot"),
                               _sep(b, "l_foot", "r_foot"), delta=1.0)

    def test_side_walk_strides_horizontally(self):
        still = p3.pose3d(60, 120, 80, 0.0, 90)
        mid = p3.pose3d(60, 120, 80, math.pi / 2, 90)
        self.assertGreater(_sep(mid, "l_foot", "r_foot"),
                           _sep(still, "l_foot", "r_foot") + 5)


class TestFacingFromDelta(unittest.TestCase):
    def test_headings(self):
        self.assertAlmostEqual(p3.facing_from_delta(0, 1), 0.0)      # south/front
        self.assertAlmostEqual(p3.facing_from_delta(1, 0), 90.0)     # east
        self.assertAlmostEqual(p3.facing_from_delta(0, -1), 180.0)   # north/back
        self.assertAlmostEqual(p3.facing_from_delta(-1, 0), 270.0)   # west


if __name__ == "__main__":
    unittest.main()
