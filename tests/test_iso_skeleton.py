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
        old = isk._CLIP.get("idle")
        isk._CLIP["idle"] = "no_such_clip"
        try:
            self.assertIsNone(
                isk.sample_figure("idle", 0.0, (1, 1, 1), (1, 1, 1), 2))
        finally:
            isk._CLIP["idle"] = old

    def test_walk_frames_differ(self):
        a = isk.sample_figure("walk", 0.25, (1,) * 3, (1,) * 3, 2)
        b = isk.sample_figure("walk", 0.75, (1,) * 3, (1,) * 3, 2)
        # a leg-bone vertex set differs between opposite stride phases
        self.assertGreater(
            float(np.abs(np.asarray(a[0][0]) - np.asarray(b[0][0])).max()),
            0.05)


if __name__ == "__main__":
    unittest.main()
