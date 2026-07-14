"""P34.8 — the Mixamo mocap clips baked to data/anim + the runtime poser."""

import os as _os
import tempfile as _tempfile
_os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
_os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_mo_"))

import glob
import json
import os
import unittest

from ui import char_mocap as mc

_ANIM = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "data", "anim")


class TestBakedData(unittest.TestCase):
    def test_all_clips_well_formed(self):
        files = glob.glob(os.path.join(_ANIM, "*.json"))
        self.assertGreaterEqual(len(files), 12)
        for f in files:
            d = json.load(open(f))
            for k in ("clip", "fps", "loop", "keys", "joints"):
                self.assertIn(k, d, f)
            self.assertEqual(len(d["joints"]), 15, f)
            for j, arr in d["joints"].items():
                self.assertEqual(len(arr), d["keys"], f"{f}:{j}")
                self.assertEqual(len(arr[0]), 2, f)

    def test_walk_feet_are_out_of_phase(self):
        d = json.load(open(os.path.join(_ANIM, "walk.json")))
        lf = [p[0] for p in d["joints"]["l_foot"]]
        rf = [p[0] for p in d["joints"]["r_foot"]]
        # when the left foot is most forward, the right is well behind it
        i = lf.index(max(lf))
        self.assertGreater(lf[i], rf[i])


class TestPoser(unittest.TestCase):
    def test_clip_for(self):
        self.assertEqual(mc.clip_for("walk"), "walk")
        self.assertEqual(mc.clip_for("run"), "run")
        self.assertIsNone(mc.clip_for("no_such_action"))

    def test_is_loop(self):
        self.assertTrue(mc.is_loop("walk"))
        self.assertFalse(mc.is_loop("jump"))

    def test_pose_maps_to_screen(self):
        pose = mc.pose_from_clip("walk", 0.0, 100, 300, 60, (1, 0))
        self.assertEqual(len(pose["head_r"] and pose), len(pose))
        for j in ("l_foot", "r_foot", "head", "l_hand", "r_hand"):
            self.assertIn(j, pose)
        self.assertLess(pose["head"][1], pose["l_foot"][1])   # head above feet
        # feet rest near the anchor (ny≈0 → y≈foot_y)
        self.assertLess(abs(pose["l_foot"][1] - 300), 60 * 0.2)

    def test_facing_mirrors_x(self):
        r = mc.pose_from_clip("walk", 0.25, 100, 300, 60, (1, 0))
        left = mc.pose_from_clip("walk", 0.25, 100, 300, 60, (-1, 0))
        # a joint offset from centre flips side with facing
        self.assertAlmostEqual((r["l_hand"][0] - 100), -(left["l_hand"][0] - 100),
                               delta=1)

    def test_interpolates_between_keys(self):
        a = mc.pose_from_clip("walk", 0.0, 100, 300, 60, (1, 0))
        mid = mc.pose_from_clip("walk", 0.5 / 16, 100, 300, 60, (1, 0))
        self.assertNotEqual(a["l_foot"], mid["l_foot"])


if __name__ == "__main__":
    unittest.main()
