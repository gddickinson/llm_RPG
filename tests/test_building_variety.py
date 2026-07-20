"""OAKVALE T8 — per-building style variety (pure, headless)."""

import unittest

from ui import building_variety as bv


class TestVariety(unittest.TestCase):
    def _base(self):
        return {"wall": "stone", "covering": "slate", "roof": "gable",
                "chimneys": 1}

    def test_deterministic_per_position(self):
        a = bv.variant_style(self._base(), "home", 12, 7)
        b = bv.variant_style(self._base(), "home", 12, 7)
        self.assertEqual(a, b, "a building looks the same every frame")

    def test_clones_differ(self):
        seen = set()
        for wx in range(20):
            s = bv.variant_style(self._base(), "home", wx, 5)
            seen.add((s["wall"], s["covering"]))
        self.assertGreater(len(seen), 1, "neighbouring houses differ")

    def test_humble_homes_get_humble_materials(self):
        for wx in range(30):
            s = bv.variant_style(self._base(), "cottage", wx, 3)
            self.assertIn(s["covering"], ("thatch", "shingle", "clay"))
            self.assertIn(s["wall"], ("timber", "wood", "brick"))

    def test_sacred_stays_stone_and_slate(self):
        for wx in range(30):
            s = bv.variant_style(self._base(), "cathedral", wx, 9)
            self.assertIn(s["covering"], ("slate", "lead", "stone"))
            self.assertIn(s["wall"], ("stone", "brick"))

    def test_roof_shape_is_preserved(self):
        s = bv.variant_style(self._base(), "home", 1, 1)
        self.assertEqual(s["roof"], "gable", "variety changes skin, not shape")

    def test_window_shape_from_class_palette(self):
        for wx in range(20):
            sh = bv.window_shape("cathedral", "square", wx, 2)
            self.assertIn(sh, ("lancet", "rose", "arched"))
        # deterministic
        self.assertEqual(bv.window_shape("home", "square", 4, 4),
                         bv.window_shape("home", "square", 4, 4))

    def test_unknown_kind_defaults_gracefully(self):
        s = bv.variant_style(self._base(), "nonsense", 1, 1)
        self.assertIn("covering", s)
        self.assertIn("wall", s)


if __name__ == "__main__":
    unittest.main()
