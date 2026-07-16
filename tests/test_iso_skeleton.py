"""ISO.6 — Mixamo-mocap-driven rigged skeleton for iso characters (headless)."""

import unittest

import numpy as np
import pygame

from ui import iso_skeleton as isk


class TestBone(unittest.TestCase):
    def test_bone_is_a_box_along_the_segment(self):
        v, t, c = isk._bone((0, 0, 0), (0, 1, 0), 0.1, (100, 100, 100))
        self.assertEqual(len(v), 8, "a box between two joints")
        self.assertEqual(len(t), 12)
        # spans from ~0 to ~1 in y (the bone direction)
        self.assertLess(v[:, 1].min(), 0.2)
        self.assertGreater(v[:, 1].max(), 0.8)

    def test_bone_orients_along_any_axis(self):
        v, _, _ = isk._bone((0, 0, 0), (1, 0, 0), 0.1, (0, 0, 0))
        self.assertGreater(v[:, 0].max(), 0.8, "spans the x bone direction")


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
