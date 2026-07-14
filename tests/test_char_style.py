"""P34.11 — per-character motion style: gait, attack style, cast gesture, and
their effect on the built pose."""

import os as _os
import tempfile as _tempfile
_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_cs_"))

import unittest

from ui import char_style as st
from ui.char_pose import build_pose


class _C:
    def __init__(self, cid):
        self.id = cid


class TestGait(unittest.TestCase):
    def test_shape_and_range(self):
        g = st.gait_of(_C("someone"))
        for k in ("stride", "bob", "arm", "cadence"):
            self.assertIn(k, g)
            self.assertGreater(g[k], 0.5)
            self.assertLess(g[k], 2.0)

    def test_stable_per_id(self):
        self.assertEqual(st.gait_of(_C("dora")), st.gait_of(_C("dora")))

    def test_varies_across_a_crowd(self):
        seen = {tuple(sorted(st.gait_of(_C(c)).items()))
                for c in ("a", "bb", "ccc", "dddd", "eeeee", "ffffff",
                          "ggg", "hhh", "iii", "jjj", "kkk", "lll")}
        self.assertGreaterEqual(len(seen), 4)      # a real spread


class TestAttackStyle(unittest.TestCase):
    def test_weapon_forced_styles(self):
        self.assertEqual(st.attack_style(_C("x"), "axe"), "overhead")
        self.assertEqual(st.attack_style(_C("x"), "mace"), "overhead")
        self.assertEqual(st.attack_style(_C("x"), "dagger"), "thrust")
        self.assertEqual(st.attack_style(_C("x"), "spear"), "thrust")

    def test_free_weapon_varies_but_is_valid_and_stable(self):
        for cid in ("al", "bo", "ci", "du", "ev"):
            s = st.attack_style(_C(cid), "sword")
            self.assertIn(s, ("overhead", "slash", "thrust"))
            self.assertEqual(s, st.attack_style(_C(cid), "sword"))


class TestCastStyle(unittest.TestCase):
    def test_staff_slams(self):
        self.assertEqual(st.cast_style(_C("x"), "staff"), "cast_staff")

    def test_others_point_or_two_hand(self):
        for cid in ("mage1", "mage2", "mage3"):
            self.assertIn(st.cast_style(_C(cid), None), ("cast", "cast_point"))


class TestPoseEffect(unittest.TestCase):
    def test_gait_changes_the_stride(self):
        base = build_pose(100, 300, 80, walk=1.2, moving=True, facing=(0, 1))
        longg = build_pose(100, 300, 80, walk=1.2, moving=True, facing=(0, 1),
                           gait={"stride": 1.6, "bob": 1.0, "arm": 1.0,
                                 "cadence": 1.0})

        def foot_off(p):
            return abs(p["l_foot"][0] - p["l_hip"][0])
        self.assertGreater(foot_off(longg), foot_off(base) + 1.0)

    def test_attack_styles_are_distinct(self):
        kw = dict(attack=0.45, facing=(1, 0))
        oh = build_pose(100, 300, 80, attack_style="overhead", **kw)
        th = build_pose(100, 300, 80, attack_style="thrust", **kw)
        sl = build_pose(100, 300, 80, attack_style="slash", **kw)
        # overhead strikes ABOVE the shoulder; thrust is a level jab (lower)
        self.assertLess(oh["r_hand"][1], oh["r_sh"][1])
        self.assertGreater(th["r_hand"][1], oh["r_hand"][1])
        # all three hands land in different places
        self.assertNotEqual(oh["r_hand"], th["r_hand"])
        self.assertNotEqual(oh["r_hand"], sl["r_hand"])
        self.assertNotEqual(th["r_hand"], sl["r_hand"])

    def test_neutral_gait_matches_default(self):
        a = build_pose(100, 300, 80, walk=0.9, moving=True, facing=(1, 0))
        b = build_pose(100, 300, 80, walk=0.9, moving=True, facing=(1, 0),
                       gait={"stride": 1.0, "bob": 1.0, "arm": 1.0,
                             "cadence": 1.0}, attack_style="overhead")
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
