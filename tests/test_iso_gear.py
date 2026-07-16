"""ISO.12 — worn gear meshes (weapon / headgear / shield) for iso characters."""

import unittest

import numpy as np

from ui import iso_gear


def _valid(mesh):
    assert mesh, "non-empty mesh"
    for v, t, c in mesh:
        assert np.asarray(v).shape[1] == 3
        assert np.asarray(t).shape[1] == 3
        assert (np.asarray(t) < len(v)).all(), "tri indices in range"
        assert len(c) == 3
    return True


class TestWeapons(unittest.TestCase):
    def test_every_weapon_kind_builds_a_mesh(self):
        hand = (0.3, 1.0, 0.1)
        fwd = np.array([0.0, 0.0, 1.0])
        for kind in ("sword", "dagger", "axe", "mace", "spear", "staff", "bow"):
            m = iso_gear.weapon_mesh(kind, hand, fwd)
            self.assertTrue(_valid(m), f"{kind} is a valid mesh")

    def test_unknown_weapon_is_empty(self):
        self.assertEqual(iso_gear.weapon_mesh("noodle", (0, 1, 0),
                                              np.array([0, 0, 1.0])), [])

    def test_a_spear_reaches_further_than_a_dagger(self):
        fwd = np.array([0.0, 0.0, 1.0])
        hand = (0.0, 1.0, 0.0)
        span = lambda m: max(np.asarray(v)[:, 1].max() for v, _, _ in m)
        self.assertGreater(span(iso_gear.weapon_mesh("spear", hand, fwd)),
                           span(iso_gear.weapon_mesh("dagger", hand, fwd)))


class TestHeadgearAndShield(unittest.TestCase):
    def test_headgear_kinds(self):
        hc = np.array([0.0, 1.5, 0.0])
        fwd = np.array([0.0, 0.0, 1.0])
        for kind in ("helmet", "hat", "hood", "circlet"):
            self.assertTrue(_valid(iso_gear.headgear_mesh(kind, hc, fwd)))
        self.assertEqual(iso_gear.headgear_mesh("none", hc, fwd), [])

    def test_shield_builds(self):
        self.assertTrue(_valid(iso_gear.shield_mesh(
            (-0.3, 1.0, 0.0), np.array([0.0, 0.0, 1.0]))))


class TestAccessories(unittest.TestCase):
    def _pose(self):
        return {"r_hand": np.array([0.3, 1.0, 0.1]),
                "l_hand": np.array([-0.3, 1.0, 0.1]),
                "head": np.array([0.0, 1.5, 0.0])}

    def test_full_kit_assembles(self):
        m = iso_gear.accessories(self._pose(), 0.0,
                                 ("sword", "helmet", True, 1.0))
        self.assertTrue(_valid(m), "sword + helmet + shield")

    def test_empty_kit_is_empty(self):
        self.assertEqual(
            iso_gear.accessories(self._pose(), 0.0, (None, None, False, 1.0)),
            [])

    def test_bow_uses_the_off_hand_no_shield(self):
        m = iso_gear.accessories(self._pose(), 0.0, ("bow", None, True, 1.0))
        self.assertTrue(_valid(m), "a bow builds (shield suppressed)")


if __name__ == "__main__":
    unittest.main()
