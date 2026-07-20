"""OAKVALE T7 — terrain-aware ROAD routing (A* over a cost-field).

Adapted from `autonomous_world/road_pathfinder.py`: route a road between two
points as least-cost A* over the tile grid, where flat grass is cheap, forest
dearer, hills/mountains expensive, and water crossable but costly — so a road
follows the easy ground, skirts the hills, and BRIDGES a river at its narrowest
rather than running miles around it. `find_road_path` returns the tile path;
`lay_road` stamps it (ROAD on land, BRIDGE over water), keeping buildings.
"""

import heapq
from typing import List, Optional, Tuple

from world.world_map import TerrainType

# per-terrain step cost — water is dear (a bridge) but not impassable
_COST = {
    TerrainType.ROAD: 0.4, TerrainType.BRIDGE: 0.4, TerrainType.GRASS: 1.0,
    TerrainType.FARMLAND: 1.1, TerrainType.FOREST: 2.4, TerrainType.SWAMP: 4.0,
    TerrainType.WATER: 6.0, TerrainType.MOUNTAIN: 12.0,
}
_BLOCK = (TerrainType.BUILDING,)                 # never route through a building
Pt = Tuple[int, int]


def _cost(wmap, x, y) -> float:
    return _COST.get(wmap.terrain[y][x], 1.5)


def find_road_path(wmap, start: Pt, goal: Pt,
                   max_expand: int = 40000) -> Optional[List[Pt]]:
    """Least-cost 8-connected A* from start to goal, or None."""
    W, H = wmap.width, wmap.height
    sx, sy = start
    gx, gy = goal
    if not (0 <= gx < W and 0 <= gy < H):
        return None

    def h(x, y):                                  # octile heuristic
        dx, dy = abs(x - gx), abs(y - gy)
        return (dx + dy) + (1.4142 - 2) * min(dx, dy)

    open_h = [(h(sx, sy), 0.0, (sx, sy))]
    came = {}
    best = {(sx, sy): 0.0}
    expanded = 0
    while open_h and expanded < max_expand:
        _, g, (x, y) = heapq.heappop(open_h)
        expanded += 1
        if (x, y) == (gx, gy):
            path = [(x, y)]
            while (x, y) in came:
                x, y = came[(x, y)]
                path.append((x, y))
            return path[::-1]
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                nx, ny = x + dx, y + dy
                if not (0 <= nx < W and 0 <= ny < H):
                    continue
                if wmap.terrain[ny][nx] in _BLOCK and (nx, ny) != (gx, gy):
                    continue
                step = _cost(wmap, nx, ny) * (1.4142 if dx and dy else 1.0)
                ng = g + step
                if ng < best.get((nx, ny), 1e18):
                    best[(nx, ny)] = ng
                    came[(nx, ny)] = (x, y)
                    heapq.heappush(open_h, (ng + h(nx, ny), ng, (nx, ny)))
    return None


def lay_road(wmap, path: List[Pt]) -> int:
    """Stamp a path as ROAD (BRIDGE over water); never overwrite a building.
    Returns how many bridge tiles were laid."""
    bridges = 0
    for (x, y) in path or []:
        if not (0 <= x < wmap.width and 0 <= y < wmap.height):
            continue
        t = wmap.terrain[y][x]
        if t == TerrainType.BUILDING:
            continue
        if t == TerrainType.WATER:
            wmap.terrain[y][x] = TerrainType.BRIDGE
            bridges += 1
        elif t != TerrainType.BRIDGE:
            wmap.terrain[y][x] = TerrainType.ROAD
    return bridges


def connect(wmap, start: Pt, goal: Pt) -> int:
    """Route + lay a road from start to goal; returns bridges laid (or -1 if
    no path)."""
    path = find_road_path(wmap, start, goal)
    if path is None:
        return -1
    return lay_road(wmap, path)
