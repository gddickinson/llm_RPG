"""P37.3 — gate & portcullis geometry (pure, headless).

A shut town/castle gate renders as a barred PORTCULLIS in a stone arch, not a
blank wall (George). These check the pure geometry `renderer_buildings` draws.
"""

import unittest

from ui import gate_shapes as gs


class TestPortcullis(unittest.TestCase):
    def _g(self, ts=48, h=40, px=100, py=200):
        return gs.portcullis(px, py, ts, h), (ts, h, px, py)

    def test_opening_sits_within_the_front_face(self):
        g, (ts, h, px, py) = self._g()
        ox, oy, ow, oh = g["opening"]
        self.assertGreaterEqual(ox, px)
        self.assertLessEqual(ox + ow, px + ts)
        self.assertGreaterEqual(oy, py + ts - h)      # below the face top
        self.assertLessEqual(oy + oh, py + ts)        # above the ground line

    def test_has_a_grille(self):
        g, _ = self._g()
        self.assertGreaterEqual(len(g["bars_v"]), 1, "vertical bars")
        self.assertGreaterEqual(len(g["bars_h"]), 1, "cross bars")

    def test_bars_span_the_opening(self):
        g, _ = self._g()
        ox, oy, ow, oh = g["opening"]
        for (a, b) in g["bars_v"]:            # vertical bars inside, run down
            self.assertTrue(ox <= a[0] <= ox + ow)
            self.assertEqual(a[0], b[0])
            self.assertLess(a[1], b[1])
        for (a, b) in g["bars_h"]:            # cross bars span the width
            self.assertEqual(a[1], b[1])
            self.assertLessEqual(a[0], ox)
            self.assertGreaterEqual(b[0], ox + ow - 1)

    def test_frame_jambs_flank_the_opening(self):
        g, (ts, h, px, py) = self._g()
        lx, ly, lw, lh = g["frame"]["left"]
        rx, ry, rw, rh = g["frame"]["right"]
        ox = g["opening"][0]
        self.assertLessEqual(lx + lw, ox)             # left jamb left of opening
        self.assertGreaterEqual(rx, ox)               # right jamb right of it

    def test_scales_with_tile_size(self):
        small = gs.portcullis(100, 200, 16, 12)
        big = gs.portcullis(100, 200, 96, 80)
        # both have a real grille, and the big gate's opening is larger
        self.assertGreaterEqual(len(small["bars_v"]), 1)
        self.assertGreaterEqual(len(big["bars_v"]), 1)
        self.assertGreater(big["opening"][2], small["opening"][2])
        self.assertTrue(small["opening"][2] >= 1 and small["opening"][3] >= 1)

    def test_deterministic(self):
        self.assertEqual(gs.portcullis(10, 20, 48, 40),
                         gs.portcullis(10, 20, 48, 40))


if __name__ == "__main__":
    unittest.main()
