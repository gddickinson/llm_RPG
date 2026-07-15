"""Worldgen leap (P16.6) — elevation, downhill rivers, site scoring.

Ports autonomous_world's `river_gen._trace_river_path` (water follows the
land downhill) and `world_plan._score_city_location` (a good town sits
near water, among varied ground, off the map edge), adapted to our fixed
grid — no chunk streaming.

All pure and seed-reproducible: an `elevation_field` carves a meandering
low VALLEY across the map, `trace_river` follows that valley's floor
downhill from the left edge to the right (one water tile per column, its
course bending where the ground is lowest), and `score_site` / `is_shore`
give the worldgen the numbers it needs to place settlements well and to
autotile shorelines. This round wires the elevation-driven river into
`WorldGenerator`, replacing the old random-walk; site scoring + shore
autotiling are ready helpers for P16.6b.
"""

import random as _random

from world.world_map import TerrainType

VALLEY_LO = 0.35        # valley wanders between these fractions of height
VALLEY_HI = 0.65


def elevation_field(w: int, h: int, seed: int = 0) -> list:
    """A height map whose low VALLEY meanders horizontally across the
    map — deterministic from `seed`. Elevation rises away from the
    valley floor, so tracing the minimum per column follows a river."""
    rng = _random.Random(seed)
    segments = max(2, w // 12)
    centers = [rng.uniform(h * VALLEY_LO, h * VALLEY_HI)
               for _ in range(segments + 1)]
    elev = [[0.0] * w for _ in range(h)]
    for x in range(w):
        t = 0.0 if w <= 1 else x / (w - 1) * segments
        i = int(t)
        frac = t - i
        vy = centers[i] * (1 - frac) + centers[min(i + 1, segments)] * frac
        vy += rng.uniform(-0.6, 0.6)          # a little wobble
        for y in range(h):
            elev[y][x] = abs(y - vy)
    return elev


def trace_river(elev: list, w: int, h: int) -> list:
    """The river's course: from the lowest tile on the left edge, step
    right column by column, each step bending toward the lowest of the
    three tiles ahead — steepest descent, so the water hugs the valley.
    Returns one (x, y) per column, kept off the very edges."""
    lo, hi = 2, h - 3
    if hi < lo:
        lo = hi = h // 2
    y = min(range(h), key=lambda yy: elev[yy][0])
    y = max(lo, min(hi, y))
    path = [(0, y)]
    for x in range(1, w):
        cand = [ny for ny in (y - 1, y, y + 1) if lo <= ny <= hi] or [y]
        y = min(cand, key=lambda ny: elev[ny][x])
        path.append((x, y))
    return path


def is_shore(terrain: list, x: int, y: int) -> bool:
    """A land tile touching water — the P16.6b shore-autotile predicate."""
    h = len(terrain)
    w = len(terrain[0]) if h else 0
    if not (0 <= x < w and 0 <= y < h):
        return False
    if terrain[y][x] == TerrainType.WATER:
        return False
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        nx, ny = x + dx, y + dy
        if 0 <= nx < w and 0 <= ny < h and \
                terrain[ny][nx] == TerrainType.WATER:
            return True
    return False


def score_site(terrain: list, x: int, y: int, radius: int = 6) -> int:
    """How good a settlement site (x, y) is: near WATER, among VARIED
    ground, and OFF the map edge (AW's `_score_city_location`)."""
    h = len(terrain)
    w = len(terrain[0]) if h else 0
    edge_pen = 0 if (radius <= x < w - radius and
                     radius <= y < h - radius) else -5
    water = 0
    kinds = set()
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            nx, ny = x + dx, y + dy
            if 0 <= nx < w and 0 <= ny < h:
                t = terrain[ny][nx]
                kinds.add(t)
                if t == TerrainType.WATER:
                    water += 1
    return min(water, 8) + len(kinds) + edge_pen
