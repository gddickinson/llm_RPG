"""Field of view — recursive shadowcasting (P8.6, ported from
autonomous_world's cleanest module).

Octant-based shadow casting (after Bob Nystrom's "What the Hero
Sees"): walls throw shadows, shadows merge, anything fully shadowed
is unseen. Powers dungeon fog-of-war (visible / explored-but-dim /
unknown) and true line-of-sight for ranged combat (P8.7) — no more
shooting through walls.

`compute_fov` is pure (takes an is_opaque callable); `zone_fov` and
`overworld_fov` bind it to our grids: interior/dungeon walls and
closed terrain block sight; on the overworld, buildings and
mountains do.
"""

from typing import Callable, Set, Tuple


class _Shadow:
    __slots__ = ("start", "end")

    def __init__(self, start: float, end: float):
        self.start = start
        self.end = end

    def contains(self, other: "_Shadow") -> bool:
        return self.start <= other.start and self.end >= other.end


class _ShadowLine:
    __slots__ = ("_shadows",)

    def __init__(self):
        self._shadows = []

    def is_in_shadow(self, projection: _Shadow) -> bool:
        return any(s.contains(projection) for s in self._shadows)

    def is_full(self) -> bool:
        return (len(self._shadows) == 1 and
                self._shadows[0].start <= 0 and
                self._shadows[0].end >= 1)

    def add(self, shadow: _Shadow) -> None:
        index = 0
        for i, existing in enumerate(self._shadows):
            if existing.start >= shadow.start:
                index = i
                break
            index = i + 1
        overlaps_prev = (index > 0 and
                         self._shadows[index - 1].end >= shadow.start)
        overlaps_next = (index < len(self._shadows) and
                         self._shadows[index].start <= shadow.end)
        if overlaps_next:
            if overlaps_prev:
                self._shadows[index - 1].end = max(
                    self._shadows[index - 1].end, shadow.end,
                    self._shadows[index].end)
                del self._shadows[index]
            else:
                self._shadows[index].start = min(
                    self._shadows[index].start, shadow.start)
                self._shadows[index].end = max(
                    self._shadows[index].end, shadow.end)
        elif overlaps_prev:
            self._shadows[index - 1].end = max(
                self._shadows[index - 1].end, shadow.end)
        else:
            self._shadows.insert(index, shadow)


def _project_tile(row: int, col: int) -> _Shadow:
    return _Shadow(col / (row + 2), (col + 1) / (row + 1))


_OCTANTS = (
    lambda r, c: (c, -r), lambda r, c: (r, -c),
    lambda r, c: (r, c), lambda r, c: (c, r),
    lambda r, c: (-c, r), lambda r, c: (-r, c),
    lambda r, c: (-r, -c), lambda r, c: (-c, -r),
)


def compute_fov(ox: int, oy: int, radius: int,
                is_opaque: Callable[[int, int], bool],
                width: int, height: int) -> Set[Tuple[int, int]]:
    """All tiles visible from (ox, oy) within radius."""
    visible = {(ox, oy)}
    max_r2 = radius * radius
    for transform in _OCTANTS:
        line = _ShadowLine()
        for row in range(1, radius + 1):
            if line.is_full():
                break
            for col in range(row + 1):
                dx, dy = transform(row, col)
                tx, ty = ox + dx, oy + dy
                if not (0 <= tx < width and 0 <= ty < height):
                    continue
                if dx * dx + dy * dy > max_r2:
                    continue
                projection = _project_tile(row, col)
                if line.is_in_shadow(projection):
                    continue
                visible.add((tx, ty))
                if is_opaque(tx, ty):
                    line.add(projection)
    return visible


def has_line_of_sight(ax: int, ay: int, bx: int, by: int,
                      is_opaque: Callable[[int, int], bool],
                      width: int, height: int,
                      max_radius: int = 12) -> bool:
    """Can A see B? (B visible from A's FOV.)"""
    if abs(ax - bx) > max_radius or abs(ay - by) > max_radius:
        return False
    return (bx, by) in compute_fov(ax, ay, max_radius, is_opaque,
                                   width, height)


# ------------------------------------------------- llm_RPG bindings

def _zone_opaque(zone) -> Callable[[int, int], bool]:
    from world.world_map import TerrainType

    def is_opaque(x: int, y: int) -> bool:
        if not (0 <= x < zone.width and 0 <= y < zone.height):
            return True
        return zone.terrain[y][x] in (TerrainType.BUILDING,
                                      TerrainType.MOUNTAIN)
    return is_opaque


def _overworld_opaque(wmap) -> Callable[[int, int], bool]:
    from world.world_map import TerrainType

    def is_opaque(x: int, y: int) -> bool:
        if not (0 <= x < wmap.width and 0 <= y < wmap.height):
            return True
        return wmap.terrain[y][x] in (TerrainType.BUILDING,
                                      TerrainType.MOUNTAIN)
    return is_opaque


def zone_fov(zone, origin: Tuple[int, int],
             radius: int = 8) -> Set[Tuple[int, int]]:
    return compute_fov(origin[0], origin[1], radius,
                       _zone_opaque(zone), zone.width, zone.height)


def overworld_los(engine, a: Tuple[int, int], b: Tuple[int, int],
                  max_radius: int = 12) -> bool:
    wmap = engine.world.map
    return has_line_of_sight(a[0], a[1], b[0], b[1],
                             _overworld_opaque(wmap),
                             wmap.width, wmap.height, max_radius)
