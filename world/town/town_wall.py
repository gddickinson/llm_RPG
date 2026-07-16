"""OAKVALE T3 — the DEFENDED CORE: a wall around the inner districts + gates.

Adapted from `autonomous_world/wall_generation.py`: a curtain wall is a
slightly-organic POLYGON around the town's inner core (the civic/market/temple
wards, ~half the town radius), Laplacian-smoothed so it reads as a medieval
enceinte rather than a circle. The elegant part is GATES — placed exactly where
a MAIN BOULEVARD crosses a wall edge (segment×segment intersection), so a road
always runs THROUGH a gate, never into a blank wall. TOWERS stand at the wall's
vertices, spaced around the perimeter.

Pure geometry (points + tile sets), headless-testable. The T5 integration stamps
`wall_tiles()` as WALL (BUILDING) except at the `gates`, which become ROAD (a
gate), and plants a tower marker at each `tower_points()` — reusing the P31.1
fortify + P37.3 gate machinery. The outer districts sit OUTSIDE the wall as
suburbs; the inner core is the central defended region George asked for.
"""

import math
import random
from typing import List, Optional, Tuple

from world.town.streets import _line_tiles

Point = Tuple[float, float]


def _smooth(pts: List[Point], passes: int = 2) -> List[Point]:
    """Laplacian smoothing: each vertex eases toward its neighbours' average."""
    for _ in range(max(0, passes)):
        n = len(pts)
        out = []
        for i in range(n):
            px, py = pts[(i - 1) % n]
            nx, ny = pts[(i + 1) % n]
            cx, cy = pts[i]
            out.append((cx + 0.3 * ((px + nx) / 2 - cx),
                        cy + 0.3 * ((py + ny) / 2 - cy)))
        pts = out
    return pts


def wall_polygon(cx: float, cy: float, radius: float, frac: float = 0.5,
                 n: int = 18, seed: int = 0) -> List[Point]:
    """`n` vertices on a jittered, smoothed ring at `frac`·radius — the curtain
    wall around the inner core."""
    rng = random.Random(seed)
    r = radius * frac
    pts = []
    for i in range(n):
        a = 2 * math.pi * i / n
        rr = r * (1.0 + rng.uniform(-0.08, 0.08))
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    return _smooth(pts, 2)


def polygon_edges(pts: List[Point]):
    return [(pts[i], pts[(i + 1) % len(pts)]) for i in range(len(pts))]


def wall_tiles(pts: List[Point]):
    """Every tile on the polygon perimeter (rasterised edges)."""
    tiles = set()
    for a, b in polygon_edges(pts):
        tiles.update(_line_tiles(a[0], a[1], b[0], b[1]))
    return tiles


def _seg_intersect(p1: Point, p2: Point, p3: Point, p4: Point) -> Optional[Point]:
    """Intersection point of segments p1p2 and p3p4, or None."""
    x1, y1 = p1
    x2, y2 = p2
    x3, y3 = p3
    x4, y4 = p4
    den = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(den) < 1e-9:
        return None
    t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / den
    u = ((x1 - x3) * (y1 - y2) - (y1 - y3) * (x1 - x2)) / den
    if 0 <= t <= 1 and 0 <= u <= 1:
        return (x1 + t * (x2 - x1), y1 + t * (y2 - y1))
    return None


def _dedupe(points, min_gap: int = 4):
    """Drop points closer than `min_gap` to one already kept."""
    out = []
    for p in points:
        if all(abs(p[0] - q[0]) + abs(p[1] - q[1]) >= min_gap for q in out):
            out.append(p)
    return out


def gates_at_crossings(pts: List[Point], street_plan) -> List[Tuple[int, int]]:
    """Gate tiles where a MAIN boulevard crosses the wall polygon — so a road
    always passes through a gate. Falls back to the polygon's compass extremes
    if too few main roads cross (keeps ≥3 gates on different sides)."""
    edges = polygon_edges(pts)
    hits = []
    for seg in getattr(street_plan, "segments", []):
        if seg.kind != "main":
            continue
        for (a, b) in edges:
            h = _seg_intersect((seg.x1, seg.y1), (seg.x2, seg.y2), a, b)
            if h is not None:
                hits.append((int(round(h[0])), int(round(h[1]))))
    gates = _dedupe(hits, min_gap=5)
    if len(gates) < 3:                          # ensure a walled core isn't a box
        cx = sum(p[0] for p in pts) / len(pts)
        cy = sum(p[1] for p in pts) / len(pts)
        extremes = {
            "n": min(pts, key=lambda p: p[1]), "s": max(pts, key=lambda p: p[1]),
            "w": min(pts, key=lambda p: p[0]), "e": max(pts, key=lambda p: p[0])}
        for p in extremes.values():
            gates.append((int(round(p[0])), int(round(p[1]))))
        gates = _dedupe(gates, min_gap=5)
    return gates


def tower_points(pts: List[Point], count: int = 8) -> List[Tuple[int, int]]:
    """Up to `count` towers spaced evenly around the wall's vertices."""
    n = len(pts)
    if n == 0:
        return []
    step = max(1, n // count)
    towers = [(int(round(pts[i][0])), int(round(pts[i][1])))
              for i in range(0, n, step)]
    return _dedupe(towers, min_gap=3)


class CoreWall:
    """The finished defended-core wall: its ring tiles, gates and towers."""

    def __init__(self, polygon, street_plan):
        self.polygon = polygon
        self.gates = gates_at_crossings(polygon, street_plan)
        self.towers = tower_points(polygon)
        gateset = set(self.gates)
        # a gate is a GAP: wall tiles minus the gate tiles (and their immediate
        # neighbours) so the boulevard can pass through the opening
        gaps = set(gateset)
        for gx, gy in self.gates:
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    gaps.add((gx + dx, gy + dy))
        self.wall = wall_tiles(polygon) - gaps

    def encloses(self, x: int, y: int) -> bool:
        """Even-odd ray cast: is (x, y) inside the wall polygon (the core)?"""
        pts = self.polygon
        inside = False
        n = len(pts)
        j = n - 1
        for i in range(n):
            xi, yi = pts[i]
            xj, yj = pts[j]
            if (yi > y) != (yj > y) and \
                    x < (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi:
                inside = not inside
            j = i
        return inside


def build_core_wall(cx, cy, radius, street_plan, frac=0.5, seed=0) -> CoreWall:
    """Wall the inner core and cut gates where the boulevards cross it."""
    poly = wall_polygon(cx, cy, radius, frac=frac, seed=seed)
    return CoreWall(poly, street_plan)
