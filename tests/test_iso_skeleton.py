"""ISO.6 — Mixamo-mocap-driven rigged skeleton for iso characters (headless)."""

import unittest

import numpy as np
import pygame

from ui import iso_skeleton as isk
from ui import char_mocap as cm


class TestBody(unittest.TestCase):
    """ISO.10 — the fleshed-out body (tapered limbs, ball joints, head+face)."""

    def test_figure_has_many_limbed_parts(self):
        pose = cm.sample_norm("idle", 0.0)
        m = isk.figure(pose, (150, 150, 165), (90, 60, 40), 0.0)
        # legs+feet+hips, torso+belt, arms+hands, head+hair+eyes+nose → many parts
        self.assertGreater(len(m), 25, "a limbed body, not a few boxes")
        for v, t, c in m:
            self.assertEqual(np.asarray(v).shape[1], 3)
            self.assertEqual(len(c), 3)

    def test_figure_spans_head_to_foot(self):
        pose = cm.sample_norm("idle", 0.0)
        m = isk.figure(pose, (150, 150, 165), (90, 60, 40), 0.0)
        ys = np.concatenate([np.asarray(v)[:, 1] for v, _, _ in m])
        self.assertLess(ys.min(), 0.2, "feet near the ground")
        self.assertGreater(ys.max(), 1.5, "head near ~1.6 tall")


class TestPose(unittest.TestCase):
    def test_lateral_spread_of_left_vs_right(self):
        self.assertLess(isk._lat("l_hip"), 0, "left is -x")
        self.assertGreater(isk._lat("r_hip"), 0, "right is +x")
        self.assertEqual(isk._lat("chest"), 0.0, "spine is centred")

    def test_pose3d_maps_joints(self):
        pn = {"l_hip": (0.0, 0.5), "r_hip": (0.0, 0.5)}
        # pose3d needs l_hip + r_hip for the pelvis
        P = isk.pose3d(pn, 2)
        self.assertIn("pelvis", P)
        self.assertEqual(len(P["l_hip"]), 3)

    def test_build_widens_the_shoulders(self):
        # a broad build spreads the shoulder/arm joints wider than a slight one
        slight = isk._lat("r_sh", 0.88)
        broad = isk._lat("r_sh", 1.14)
        self.assertGreater(broad, slight, "broader build = wider shoulders")

    def test_build_is_stable_per_person(self):
        c = type("C", (), {"id": "bertram"})()
        self.assertEqual(isk.build_of(c), isk.build_of(c))
        self.assertIn(isk.build_of(c), (0.88, 1.0, 1.14))


class TestFigure(unittest.TestCase):
    def setUp(self):
        pygame.init()

    def test_sample_figure_from_a_real_clip(self):
        m = isk.sample_figure("walk", 0.25, (150, 150, 165), (90, 60, 40), 2)
        self.assertIsNotNone(m, "the walk clip drives a skeleton")
        self.assertGreater(len(m), 12, "legs + spine + arms + head bones")
        for v, t, c in m:
            self.assertEqual(np.asarray(v).shape[1], 3)

    def test_missing_clip_returns_none(self):
        # walk routes straight through _CLIP (idle/dance use the variant table)
        old = isk._CLIP.get("walk")
        isk._CLIP["walk"] = "no_such_clip"
        try:
            self.assertIsNone(
                isk.sample_figure("walk", 0.0, (1, 1, 1), (1, 1, 1), 2))
        finally:
            isk._CLIP["walk"] = old

    def test_walk_frames_differ(self):
        a = isk.sample_figure("walk", 0.25, (1,) * 3, (1,) * 3, 2)
        b = isk.sample_figure("walk", 0.75, (1,) * 3, (1,) * 3, 2)
        # a leg-bone vertex set differs between opposite stride phases
        self.assertGreater(
            float(np.abs(np.asarray(a[0][0]) - np.asarray(b[0][0])).max()),
            0.05)


class TestCombatMoves(unittest.TestCase):
    """ISO.13 — distinct 3D strike styles + a mid-swing that moves the arm."""

    def _hand(self, style, phase):
        # the r_hand joint of the swung pose (weapon rides it)
        P = isk._apply_height(
            isk.pose3d(isk.cm.sample_norm("idle", 0.0), 0.0, 1.0), None)
        return isk._swing_arm(P, style, phase, 0.0)["r_hand"]

    def test_the_three_styles_move_the_hand_apart(self):
        # at the windup (early phase) the styles hold the hand in distinct
        # places (they cross near neutral only mid-swing)
        pts = [self._hand(s, 0.15) for s in ("overhead", "slash", "thrust")]
        for i in range(3):
            for j in range(i + 1, 3):
                self.assertGreater(float(np.linalg.norm(pts[i] - pts[j])), 0.1,
                                   "each strike style holds the hand elsewhere")

    def test_the_swing_moves_over_its_arc(self):
        a = self._hand("overhead", 0.1)
        b = self._hand("overhead", 0.9)
        self.assertGreater(float(np.linalg.norm(a - b)), 0.2, "the arm swings")

    def test_attack_figure_builds_a_body(self):
        m = isk.sample_figure("attack", 0.5, (150, 150, 165), (90, 60, 40),
                              0.0, 1.0, 0, ("sword", None, False, 1.0), "slash")
        self.assertIsNotNone(m)
        self.assertGreater(len(m), 20, "a full body + a sword")


if __name__ == "__main__":
    unittest.main()
