"""OAKVALE T2 — the STREET NETWORK of a large town.

Adapted from `autonomous_world/street_layout.py`: a town's streets are a
size-scaled TEMPLATE, not a raw grid — main BOULEVARDS crossing the centre, a
polygonal RING road partway out, RADIAL lanes spoking from the ring to the edge,
a small core GRID for big towns, and a reserved central MARKET SQUARE (plaza)
the civic core sits around. Roads carry a hierarchy (main/ring/lane) → a width,
so boulevards read wider than alleys.

Pure + deterministic (seeded), headless-testable. `plan_streets(...)` returns a
`StreetPlan` of segments + the square; `road_tiles()` rasterises every segment
(Bresenham + width) to a `{(x,y): kind}` map the T4 lot placer and the T5
integration stamp onto the world (ROAD, or a BRIDGE where a road must cross
water — handled at stamp time).
"""

import math
import random
from typing import Dict, List, Tuple

# road hierarchy → rasterised half-width (tiles either side of the centre-line)
WIDTH = {"main": 1, "ring": 1, "lane": 0, "grid": 0}
_SIZE_RING = {"village": 0.0, "town": 0.62, "city": 0.58}
_SIZE_RADIALS = {"village": 3, "town": 5, "city": 7}
_SIZE_GRID = {"village": 0, "town": 0, "city": 2}    # core grid streets each way


def _line_tiles(x1, y1, x2, y2) -> List[Tuple[int, int]]:
    """Integer Bresenham line tiles from (x1,y1) to (x2,y2)."""
    x1, y1, x2, y2 = int(round(x1)), int(round(y1)), int(round(x2)), int(round(y2))
    tiles = []
    dx, dy = abs(x2 - x1), abs(y2 - y1)
    sx, sy = (1 if x1 < x2 else -1), (1 if y1 < y2 else -1)
    err = dx - dy
    x, y = x1, y1
    while True:
        tiles.append((x, y))
        if x == x2 and y == y2:
            break
        e2 = 2 * err
        if e2 > -dy:
            err -= dy
            x += sx
        if e2 < dx:
            err += dx
            y += sy
    return tiles


def _thicken(tiles, half) -> List[Tuple[int, int]]:
    """Widen a centre-line by `half` tiles on every side (a square brush)."""
    if half <= 0:
        return list(tiles)
    out = set()
    for (x, y) in tiles:
        for dx in range(-half, half + 1):
            for dy in range(-half, half + 1):
                out.add((x + dx, y + dy))
    return list(out)


def _ngon(cx, cy, r, n, rot=0.0) -> List[Tuple[float, float]]:
    """`n` points on a circle radius `r` — a polygon approximating a ring."""
    return [(cx + r * math.cos(rot + 2 * math.pi * i / n),
             cy + r * math.sin(rot + 2 * math.pi * i / n)) for i in range(n)]


class Segment:
    __slots__ = ("x1", "y1", "x2", "y2", "kind")

    def __init__(self, x1, y1, x2, y2, kind):
        self.x1, self.y1, self.x2, self.y2, self.kind = x1, y1, x2, y2, kind

    def tiles(self) -> List[Tuple[int, int]]:
        return _thicken(_line_tiles(self.x1, self.y1, self.x2, self.y2),
                        WIDTH.get(self.kind, 0))


class StreetPlan:
    def __init__(self, cx, cy, radius, segments, square_r):
        self.cx, self.cy, self.radius = cx, cy, radius
        self.segments: List[Segment] = segments
        self.square_r = square_r                 # central market-square radius

    def square_tiles(self) -> List[Tuple[int, int]]:
        r = self.square_r
        out = []
        for dy in range(-int(r), int(r) + 1):
            for dx in range(-int(r), int(r) + 1):
                if dx * dx + dy * dy <= r * r:
                    out.append((int(self.cx) + dx, int(self.cy) + dy))
        return out

    def road_tiles(self, clip_radius: float = None) -> Dict[Tuple[int, int], str]:
        """{(x,y): kind} for every street tile (+ the plaza), clipped to the
        town disc. A denser road (main) wins over a lane on a shared tile."""
        rank = {"grid": 0, "lane": 1, "ring": 2, "main": 3, "plaza": 4}
        rr = clip_radius if clip_radius is not None else self.radius
        out: Dict[Tuple[int, int], str] = {}

        def put(x, y, kind):
            if (x - self.cx) ** 2 + (y - self.cy) ** 2 > rr * rr:
                return
            cur = out.get((x, y))
            if cur is None or rank[kind] > rank[cur]:
                out[(x, y)] = kind
        for seg in self.segments:
            for (x, y) in seg.tiles():
                put(x, y, seg.kind)
        for (x, y) in self.square_tiles():
            put(x, y, "plaza")
        return out


def plan_streets(cx: float, cy: float, radius: float, size: str = "town",
                 seed: int = 0) -> StreetPlan:
    """Lay a town's streets by size template. Deterministic in `seed`."""
    rng = random.Random(seed)
    segs: List[Segment] = []
    R = radius
    # 1) main boulevards — N-S and E-W (+ a slight jitter to the axis angle)
    for base in (0.0, math.pi / 2):
        a = base + rng.uniform(-0.12, 0.12)
        dx, dy = math.cos(a), math.sin(a)
        segs.append(Segment(cx - dx * R, cy - dy * R,
                            cx + dx * R, cy + dy * R, "main"))
    # 2) a polygonal ring road partway out
    ring_frac = _SIZE_RING.get(size, 0.6)
    if ring_frac > 0:
        pts = _ngon(cx, cy, R * ring_frac, 12, rot=rng.uniform(0, 0.5))
        for i in range(len(pts)):
            a, b = pts[i], pts[(i + 1) % len(pts)]
            segs.append(Segment(a[0], a[1], b[0], b[1], "ring"))
    # 3) radial lanes from the ring out to the disc edge
    n_rad = _SIZE_RADIALS.get(size, 5)
    for i in range(n_rad):
        a = 2 * math.pi * i / n_rad + rng.uniform(-0.15, 0.15)
        r0 = R * (ring_frac if ring_frac > 0 else 0.3)
        segs.append(Segment(cx + math.cos(a) * r0, cy + math.sin(a) * r0,
                            cx + math.cos(a) * R * 0.98,
                            cy + math.sin(a) * R * 0.98, "lane"))
    # 4) a small core grid for a big town/city
    g = _SIZE_GRID.get(size, 0)
    if g > 0:
        step = R * 0.22
        for k in range(1, g + 1):
            off = step * k
            segs.append(Segment(cx - R * 0.4, cy - off, cx + R * 0.4, cy - off, "grid"))
            segs.append(Segment(cx - R * 0.4, cy + off, cx + R * 0.4, cy + off, "grid"))
            segs.append(Segment(cx - off, cy - R * 0.4, cx - off, cy + R * 0.4, "grid"))
            segs.append(Segment(cx + off, cy - R * 0.4, cx + off, cy + R * 0.4, "grid"))
    square_r = max(2.0, R * 0.12)
    return StreetPlan(cx, cy, radius, segs, square_r)
