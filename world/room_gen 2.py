"""P36.4 procedural building interiors — BSP room subdivision.

Adapts the room-splitting idea from `building-gen/src/buildgen/layout/subdivide.py`
(rooms carved from a floor, doorways between them) into a pure, tiny BSP generator:
recursively cut a rectangle with an internal wall and punch ONE doorway through it,
so the result is a set of connected rooms — a believable multi-room floorplan instead
of one open box. Returns a wall/floor/door grid + the leaf-room rectangles for
furniture placement. Pure + seed-reproducible; `interiors` builds an Interior from it.
"""

import random

FLOOR, WALL, DOOR = 0, 1, 2


def subdivide(w, h, seed, min_room=3, max_depth=4):
    """Return (grid, rooms): `grid[y][x]` in {FLOOR, WALL, DOOR}, `rooms` a list of
    (x, y, w, h) leaf rectangles. Every room connects to the rest via a doorway."""
    rng = random.Random(seed)
    grid = [[FLOOR] * w for _ in range(h)]
    for x in range(w):
        grid[0][x] = grid[h - 1][x] = WALL
    for y in range(h):
        grid[y][0] = grid[y][w - 1] = WALL
    rooms = []

    def split(x, y, rw, rh, depth):
        can_h = rh >= 2 * min_room + 1          # room enough to split top/bottom
        can_v = rw >= 2 * min_room + 1          # ...or left/right
        if depth <= 0 or (not can_h and not can_v):
            rooms.append((x, y, rw, rh))
            return
        if can_h and can_v:
            horiz = rh > rw if abs(rh - rw) > 1 else rng.random() < 0.5
        else:
            horiz = can_h
        if horiz:
            cy = y + rng.randint(min_room, rh - min_room - 1)
            for xx in range(x, x + rw):
                grid[cy][xx] = WALL
            split(x, y, rw, cy - y, depth - 1)
            split(x, cy + 1, rw, y + rh - cy - 1, depth - 1)
        else:
            cx = x + rng.randint(min_room, rw - min_room - 1)
            for yy in range(y, y + rh):
                grid[yy][cx] = WALL
            split(x, y, cx - x, rh, depth - 1)
            split(cx + 1, y, x + rw - cx - 1, rh, depth - 1)

    split(1, 1, w - 2, h - 2, max_depth)
    _connect(grid, rng)                         # punch a spanning tree of doorways
    return grid, rooms


def _connect(grid, rng):
    """Punch doorways so every room is reachable — a spanning tree over the floor
    components (union-find), each edge a wall tile with floor on both sides."""
    h, w = len(grid), len(grid[0])
    parent = {}

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a, b):
        parent[find(a)] = find(b)

    for y in range(h):
        for x in range(w):
            if grid[y][x] == FLOOR:
                parent[(x, y)] = (x, y)
    for (x, y) in list(parent):
        for dx, dy in ((1, 0), (0, 1)):
            n = (x + dx, y + dy)
            if n in parent:
                union((x, y), n)
    cands = []
    for y in range(1, h - 1):
        for x in range(1, w - 1):
            if grid[y][x] != WALL:
                continue
            if grid[y - 1][x] == FLOOR and grid[y + 1][x] == FLOOR:
                cands.append((x, y, (x, y - 1), (x, y + 1)))
            elif grid[y][x - 1] == FLOOR and grid[y][x + 1] == FLOOR:
                cands.append((x, y, (x - 1, y), (x + 1, y)))
    rng.shuffle(cands)
    for (x, y, a, b) in cands:
        if find(a) != find(b):
            grid[y][x] = DOOR
            union(a, b)


def is_connected(grid):
    """Flood-fill: are all FLOOR/DOOR tiles reachable from the first one?"""
    h, w = len(grid), len(grid[0])
    start = next(((x, y) for y in range(h) for x in range(w)
                  if grid[y][x] != WALL), None)
    if start is None:
        return True
    seen, stack = {start}, [start]
    while stack:
        x, y = stack.pop()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if 0 <= nx < w and 0 <= ny < h and (nx, ny) not in seen \
                    and grid[ny][nx] != WALL:
                seen.add((nx, ny))
                stack.append((nx, ny))
    total = sum(1 for y in range(h) for x in range(w) if grid[y][x] != WALL)
    return len(seen) == total
