"""OAKVALE T1 — Voronoi DISTRICT wards for a large town.

Adapted from `autonomous_world/voronoi_layout.py`: scatter ward seeds in a
golden-angle "sunflower" spiral over the town disc, assign every tile to its
nearest seed (Voronoi), relax the seeds toward their ward centroids a few times
(Lloyd) so the wards come out evenly sized and organic, then classify each ward
by its distance RING from the town centre — the inner core is civic/market/
temple/guild (the part we later WALL), the middle ring residential + craft, the
outer ring residential suburbs + stables + farming.

Pure + deterministic (seeded) + numpy-vectorised; headless-testable. The result
is a `DistrictPlan` whose `type_at(x, y)` tells the T4 lot placer which building
KINDs a tile's ward should draw from (`data/town/districts.json`).
"""

import math
import random
from typing import Dict, List, Tuple

import numpy as np

GOLDEN_ANGLE = math.pi * (3.0 - math.sqrt(5.0))    # ~2.39996 rad
INNER_FRAC = 0.42                                  # inner ring: 0..0.42 r
MIDDLE_FRAC = 0.72                                 # middle ring: 0.42..0.72 r


def _districts_data() -> dict:
    from items.data_loader import load_data_file
    try:
        return load_data_file("town/districts.json") or {}
    except Exception:                                # pragma: no cover
        return {}


def sunflower_seeds(cx: float, cy: float, radius: float, n: int,
                    rng: random.Random) -> List[Tuple[float, float]]:
    """`n` ward seeds spiralled over the disc by the golden angle (even, organic
    spacing), each jittered a touch so relaxation has somewhere to move."""
    seeds = []
    for i in range(max(1, n)):
        r = radius * math.sqrt((i + 0.5) / n) * 0.86
        theta = i * GOLDEN_ANGLE
        x = cx + r * math.cos(theta) + rng.uniform(-1.0, 1.0)
        y = cy + r * math.sin(theta) + rng.uniform(-1.0, 1.0)
        seeds.append((x, y))
    return seeds


def _disc_grid(cx: float, cy: float, radius: float):
    """The integer-tile bounding box of the disc + a boolean inside-mask."""
    x0, y0 = int(math.floor(cx - radius)), int(math.floor(cy - radius))
    x1, y1 = int(math.ceil(cx + radius)), int(math.ceil(cy + radius))
    xs = np.arange(x0, x1 + 1)
    ys = np.arange(y0, y1 + 1)
    gx, gy = np.meshgrid(xs, ys)                     # (H, W)
    inside = (gx - cx) ** 2 + (gy - cy) ** 2 <= radius * radius
    return xs, ys, gx, gy, inside


def assign_wards(cx: float, cy: float, radius: float,
                 seeds: List[Tuple[float, float]]) -> Dict[Tuple[int, int], int]:
    """Every disc tile → its nearest seed's ward id (vectorised Voronoi)."""
    xs, ys, gx, gy, inside = _disc_grid(cx, cy, radius)
    sx = np.array([s[0] for s in seeds])[:, None, None]
    sy = np.array([s[1] for s in seeds])[:, None, None]
    d2 = (sx - gx) ** 2 + (sy - gy) ** 2             # (n_seeds, H, W)
    nearest = np.argmin(d2, axis=0)                  # (H, W)
    out: Dict[Tuple[int, int], int] = {}
    ys_l, xs_l = ys.tolist(), xs.tolist()
    for j, y in enumerate(ys_l):
        row_in = inside[j]
        row_w = nearest[j]
        for i, x in enumerate(xs_l):
            if row_in[i]:
                out[(x, y)] = int(row_w[i])
    return out


def lloyd_relax(cx: float, cy: float, radius: float,
                seeds: List[Tuple[float, float]],
                iterations: int = 3) -> List[Tuple[float, float]]:
    """Move each seed to the centroid of its ward, a few times — the wards even
    out into believable organic quarters."""
    for _ in range(max(0, iterations)):
        ward = assign_wards(cx, cy, radius, seeds)
        acc = [[0.0, 0.0, 0] for _ in seeds]
        for (x, y), wid in ward.items():
            acc[wid][0] += x
            acc[wid][1] += y
            acc[wid][2] += 1
        seeds = [(a[0] / a[2], a[1] / a[2]) if a[2] else s
                 for s, a in zip(seeds, acc)]
    return seeds


def _ring_of(dist: float, radius: float) -> str:
    if dist <= radius * INNER_FRAC:
        return "inner"
    if dist <= radius * MIDDLE_FRAC:
        return "middle"
    return "outer"


def classify_wards(cx: float, cy: float, radius: float,
                   seeds: List[Tuple[float, float]], rings: dict,
                   rng: random.Random) -> Dict[int, str]:
    """Give each ward a district TYPE drawn from its distance ring's list."""
    out: Dict[int, str] = {}
    for i, (sxi, syi) in enumerate(seeds):
        ring = _ring_of(math.hypot(sxi - cx, syi - cy), radius)
        choices = rings.get(ring) or rings.get("outer") or ["residential"]
        out[i] = rng.choice(choices)
    return out


class DistrictPlan:
    """The finished ward plan: which district TYPE each town tile belongs to."""

    def __init__(self, cx, cy, radius, ward_map, ward_types, seeds):
        self.cx, self.cy, self.radius = cx, cy, radius
        self.ward_map = ward_map               # {(x,y): ward_id}
        self.ward_types = ward_types           # {ward_id: district_type}
        self.seeds = seeds                     # [(x,y)] final seed positions

    def type_at(self, x: int, y: int):
        wid = self.ward_map.get((int(x), int(y)))
        return self.ward_types.get(wid) if wid is not None else None

    def ring_at(self, x: int, y: int) -> str:
        return _ring_of(math.hypot(x - self.cx, y - self.cy), self.radius)

    def types_present(self):
        return set(self.ward_types.values())

    def tiles_of_type(self, dtype: str):
        return [xy for xy, wid in self.ward_map.items()
                if self.ward_types.get(wid) == dtype]


def plan_districts(cx: float, cy: float, radius: float, seed: int = 0,
                   size: str = "town", n_wards: int = None) -> DistrictPlan:
    """Plan a town's districts: sunflower seeds → Lloyd-relaxed Voronoi wards →
    ring classification. Deterministic in `seed`."""
    data = _districts_data()
    rings = data.get("rings") or {}
    if n_wards is None:
        n_wards = (data.get("ward_seeds") or {}).get(size, 22)
    rng = random.Random(seed)
    seeds = sunflower_seeds(cx, cy, radius, n_wards, rng)
    seeds = lloyd_relax(cx, cy, radius, seeds, iterations=3)
    ward_map = assign_wards(cx, cy, radius, seeds)
    ward_types = classify_wards(cx, cy, radius, seeds, rings, rng)
    return DistrictPlan(cx, cy, radius, ward_map, ward_types, seeds)
