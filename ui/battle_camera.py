"""Battle camera (P17.4) — the zoom/pan/LOD math, pure.

The battle screen watches a field far larger than a room, so it
needs a real camera: a float centre in tile coordinates, a
tile_size that steps through {8, 16, 32, 48}px, and a level-of-
detail switch — below 16px there is no room to draw a man, so the
screen paints one blob per squad instead of every soldier.

All of that is arithmetic with no pygame in it, so it lives here
and is unit-tested directly; `ui/battle_screen.py` owns only the
drawing.
"""

from typing import Tuple

TILE_SIZES = (8, 16, 32, 48)
DEFAULT_TILE = 32
# below this tile size a soldier is sub-pixel — draw squad blobs
LOD_BLOB_BELOW = 16

# a distinct glyph per unit category, so an icon reads as WHO it is,
# not only which side (team is the fill colour). Shapes: circle,
# triangle (advancing horse), diamond (bow), square (engine),
# hex (beast), cross (medic).
CATEGORY_SHAPE = {
    "infantry": "circle",
    "cavalry": "triangle",
    "archer": "diamond",
    "siege": "square",
    "beast": "hex",
    "support": "cross",
}


def category_shape(category: str) -> str:
    return CATEGORY_SHAPE.get(category, "circle")


def marker_points(shape: str, cx: float, cy: float, r: float) -> list:
    """Polygon vertices for a unit glyph. [] for circle/cross (which
    the renderer draws specially). Pure geometry — unit-tested."""
    if shape == "triangle":                 # points right (advancing)
        return [(cx + r, cy), (cx - r, cy - r), (cx - r, cy + r)]
    if shape == "diamond":
        return [(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)]
    if shape == "square":
        return [(cx - r, cy - r), (cx + r, cy - r),
                (cx + r, cy + r), (cx - r, cy + r)]
    if shape == "hex":
        h = r * 0.87
        return [(cx - r, cy), (cx - r / 2, cy - h), (cx + r / 2, cy - h),
                (cx + r, cy), (cx + r / 2, cy + h), (cx - r / 2, cy + h)]
    return []


class BattleCamera:
    def __init__(self, field_w: int, field_h: int,
                 view_w: int, view_h: int,
                 tile_size: int = DEFAULT_TILE):
        self.fw = field_w
        self.fh = field_h
        self.vw = view_w
        self.vh = view_h
        self.tile_size = self._snap(tile_size)
        self.cx = field_w / 2.0        # camera centre, tile coords
        self.cy = field_h / 2.0
        self.clamp()

    # ---- zoom ----------------------------------------------------

    @staticmethod
    def _snap(ts: int) -> int:
        return min(TILE_SIZES, key=lambda t: abs(t - ts))

    def _zoom_index(self) -> int:
        return TILE_SIZES.index(self.tile_size)

    def zoom_in(self) -> None:
        i = min(len(TILE_SIZES) - 1, self._zoom_index() + 1)
        self.tile_size = TILE_SIZES[i]
        self.clamp()

    def zoom_out(self) -> None:
        i = max(0, self._zoom_index() - 1)
        self.tile_size = TILE_SIZES[i]
        self.clamp()

    @property
    def blob_mode(self) -> bool:
        """True when soldiers are too small to draw individually."""
        return self.tile_size < LOD_BLOB_BELOW

    # ---- pan -----------------------------------------------------

    def pan(self, dx_tiles: float, dy_tiles: float) -> None:
        self.cx += dx_tiles
        self.cy += dy_tiles
        self.clamp()

    def center_on(self, wx: float, wy: float) -> None:
        self.cx, self.cy = float(wx), float(wy)
        self.clamp()

    def clamp(self) -> None:
        self.cx = max(0.0, min(float(self.fw), self.cx))
        self.cy = max(0.0, min(float(self.fh), self.cy))

    # ---- transforms ----------------------------------------------

    def world_to_screen(self, wx: float, wy: float) -> Tuple[float, float]:
        ts = self.tile_size
        sx = (wx - self.cx) * ts + self.vw / 2.0
        sy = (wy - self.cy) * ts + self.vh / 2.0
        return sx, sy

    def screen_to_world(self, sx: float, sy: float) -> Tuple[float, float]:
        ts = self.tile_size
        wx = (sx - self.vw / 2.0) / ts + self.cx
        wy = (sy - self.vh / 2.0) / ts + self.cy
        return wx, wy

    def visible_tile_bounds(self) -> Tuple[int, int, int, int]:
        """Inclusive (x0, y0, x1, y1) tile range to draw, clamped."""
        half_w = (self.vw / 2.0) / self.tile_size
        half_h = (self.vh / 2.0) / self.tile_size
        x0 = max(0, int(self.cx - half_w) - 1)
        y0 = max(0, int(self.cy - half_h) - 1)
        x1 = min(self.fw - 1, int(self.cx + half_w) + 1)
        y1 = min(self.fh - 1, int(self.cy + half_h) + 1)
        return x0, y0, x1, y1
