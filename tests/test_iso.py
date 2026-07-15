"""P41.1 — isometric projection math (pure, headless)."""

import unittest

from ui.iso import IsoProjection


class TestProjection(unittest.TestCase):
    def setUp(self):
        self.iso = IsoProjection(tile_w=64, tile_h=32, z_scale=16)

    def test_origin_tile_maps_to_origin(self):
        self.assertEqual(self.iso.world_to_screen(0, 0), (0.0, 0.0))

    def test_x_axis_goes_down_right_y_axis_down_left(self):
        # +wx moves screen right + down; +wy moves screen left + down
        sx, sy = self.iso.world_to_screen(1, 0)
        self.assertGreater(sx, 0)
        self.assertGreater(sy, 0)
        sx2, sy2 = self.iso.world_to_screen(0, 1)
        self.assertLess(sx2, 0)
        self.assertGreater(sy2, 0)

    def test_height_lifts_up_the_screen(self):
        flat = self.iso.world_to_screen(2, 2, z=0)
        high = self.iso.world_to_screen(2, 2, z=3)
        self.assertEqual(high[0], flat[0])          # same column
        self.assertLess(high[1], flat[1])           # lifted (smaller y = up)

    def test_screen_to_tile_is_the_inverse(self):
        for wx, wy in ((0, 0), (5, 3), (12, 20), (30, 7), (2, 9)):
            sx, sy = self.iso.world_to_screen(wx, wy)
            self.assertEqual(self.iso.screen_to_tile(sx, sy), (wx, wy))

    def test_screen_to_tile_respects_origin(self):
        iso = self.iso
        origin = (400, 120)
        sx, sy = iso.world_to_screen(8, 4, origin=origin)
        self.assertEqual(iso.screen_to_tile(sx, sy, origin=origin), (8, 4))


class TestGeometry(unittest.TestCase):
    def setUp(self):
        self.iso = IsoProjection(64, 32, 16)

    def test_diamond_is_a_2to1_rhombus(self):
        d = self.iso.diamond(100, 100)
        self.assertEqual(len(d), 4)
        top, right, bottom, left = d
        self.assertEqual(top, (100, 84))            # centre - th/2
        self.assertEqual(bottom, (100, 116))
        self.assertEqual(right, (132, 100))         # centre + tw/2
        self.assertEqual(left, (68, 100))
        # width : height == 2 : 1
        self.assertEqual(right[0] - left[0], 2 * (bottom[1] - top[1]))

    def test_flat_tile_has_no_cliff(self):
        self.assertEqual(self.iso.cliff_faces(100, 100, 0), [])

    def test_raised_tile_drops_two_side_faces(self):
        faces = self.iso.cliff_faces(100, 100, z=2)
        self.assertEqual(len(faces), 2)
        for f in faces:
            self.assertEqual(len(f), 4)             # quads
        # the drop is z * z_scale = 32px
        left_face = faces[0]
        self.assertEqual(left_face[3][1] - left_face[0][1], 32)


class TestDepthSort(unittest.TestCase):
    def setUp(self):
        self.iso = IsoProjection()

    def test_further_back_sorts_first(self):
        # a tile nearer the top-back (smaller wx+wy) draws before a front one
        keys = sorted([(3, 3), (0, 0), (1, 0), (5, 5)],
                      key=lambda t: self.iso.depth_key(*t))
        self.assertEqual(keys[0], (0, 0))
        self.assertEqual(keys[-1], (5, 5))

    def test_height_and_layer_break_ties(self):
        ground = self.iso.depth_key(2, 2, z=0, layer=0)
        obj = self.iso.depth_key(2, 2, z=0, layer=1)
        tall = self.iso.depth_key(2, 2, z=1, layer=0)
        self.assertLess(ground, obj)
        self.assertLess(ground, tall)

    def test_visible_tiles_are_depth_ordered_and_in_bounds(self):
        tiles = self.iso.visible_tiles(640, 480, (10, 10), 40, 40)
        self.assertTrue(tiles)
        self.assertTrue(all(0 <= x < 40 and 0 <= y < 40 for x, y in tiles))
        keys = [self.iso.depth_key(x, y) for x, y in tiles]
        self.assertEqual(keys, sorted(keys))


if __name__ == "__main__":
    unittest.main()
