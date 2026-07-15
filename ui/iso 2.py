"""P41.1 — isometric (2:1 dimetric) projection math (pure, headless-testable).

The foundation of the Phase 41 "3D-look" world: world tile (wx, wy) at height z
projects to a screen point; the tile is drawn as a shaded DIAMOND, and an
elevated tile drops CLIFF side-faces so hills read as 3D. `depth_key` orders the
whole scene back-to-front (the heart of correct iso occlusion). No pygame here —
`renderer` consumes these; `tests/test_iso.py` checks the geometry.

Convention: `world_to_screen` returns the CENTRE of the tile's top-face diamond;
+z lifts it up the screen. `screen_to_tile` is the exact ground-plane inverse
(for mouse / targeting).
"""

import math


class IsoProjection:
    def __init__(self, tile_w: int = 64, tile_h: int = 32, z_scale: int = 16):
        # 2:1 dimetric — tile_w should be 2 * tile_h for the classic look
        self.tw = tile_w
        self.th = tile_h
        self.zs = z_scale

    # ---- projection ------------------------------------------------

    def world_to_screen(self, wx, wy, z=0.0, origin=(0, 0)):
        """Tile (wx, wy) at height z → the screen centre of its top diamond."""
        ox, oy = origin
        sx = (wx - wy) * (self.tw / 2.0) + ox
        sy = (wx + wy) * (self.th / 2.0) - z * self.zs + oy
        return (sx, sy)

    def screen_to_tile(self, sx, sy, origin=(0, 0)):
        """Exact inverse on the ground plane (z=0): screen → (wx, wy) ints."""
        ox, oy = origin
        dx, dy = sx - ox, sy - oy
        fx = dx / self.tw + dy / self.th
        fy = dy / self.th - dx / self.tw
        return (int(math.floor(fx + 0.5)), int(math.floor(fy + 0.5)))

    # ---- tile geometry ---------------------------------------------

    def diamond(self, sx, sy):
        """The 4 corners (top, right, bottom, left) of the tile diamond whose
        centre is (sx, sy)."""
        hw, hh = self.tw / 2.0, self.th / 2.0
        return [(sx, sy - hh), (sx + hw, sy), (sx, sy + hh), (sx - hw, sy)]

    def cliff_faces(self, sx, sy, z):
        """The two visible SIDE faces (SW-left, SE-right) of a tile raised by z,
        dropping from the top diamond's lower edges to the ground — [] if flat.
        Each face is a 4-point quad."""
        drop = z * self.zs
        if drop <= 0:
            return []
        hw, hh = self.tw / 2.0, self.th / 2.0
        left = (sx - hw, sy)
        bottom = (sx, sy + hh)
        right = (sx + hw, sy)
        left_face = [left, bottom,
                     (bottom[0], bottom[1] + drop), (left[0], left[1] + drop)]
        right_face = [right, bottom,
                      (bottom[0], bottom[1] + drop), (right[0], right[1] + drop)]
        return [left_face, right_face]

    # ---- depth sort ------------------------------------------------

    @staticmethod
    def depth_key(wx, wy, z=0.0, layer=0):
        """Painter's-algorithm key: draw smaller (wx+wy) first (further back),
        then by height, then by layer (terrain < object < character)."""
        return (wx + wy, z, layer)

    # ---- visible range ---------------------------------------------

    def visible_tiles(self, view_w, view_h, cam_tile, world_w, world_h,
                      pad=2):
        """The (wx, wy) tiles that can fall inside a view_w×view_h window
        centred on cam_tile, in back-to-front (depth) order. A generous `pad`
        covers tall objects/cliffs that overhang their tile."""
        cx, cy = cam_tile
        # how many tiles the half-window spans on each world axis
        span_x = int(view_w / self.tw) + pad + 2
        span_y = int(view_h / self.th) + pad + 2
        out = []
        for wx in range(max(0, cx - span_x), min(world_w, cx + span_x + 1)):
            for wy in range(max(0, cy - span_y), min(world_h, cy + span_y + 1)):
                out.append((wx, wy))
        out.sort(key=lambda t: self.depth_key(t[0], t[1]))
        return out
