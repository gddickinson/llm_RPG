"""Flow fields (P17.3) — many-unit pathing, O(map) not O(units).

One multi-source BFS from a team's target tiles builds a distance
field over the whole grid; every soldier then just steps to the
adjacent tile with the lowest distance. That is the cheap,
deterministic pather that lets a hundred men advance on an
objective without a hundred path searches (Supreme Commander's
trick). Blocking tiles (walls, water) are skipped so the field
naturally routes men around them and THROUGH breaches once a wall
falls to rubble.
"""

from collections import deque
from typing import Dict, List, Optional, Tuple

_NEIGH = ((1, 0), (-1, 0), (0, 1), (0, -1),
          (1, 1), (1, -1), (-1, 1), (-1, -1))


def distance_field(field, targets: List[Tuple[int, int]]
                   ) -> Dict[Tuple[int, int], int]:
    """BFS distance from the nearest target over passable ground."""
    dist: Dict[Tuple[int, int], int] = {}
    q = deque()
    for t in targets:
        if field.in_bounds(*t):
            dist[t] = 0
            q.append(t)
    while q:
        x, y = q.popleft()
        d = dist[(x, y)]
        for dx, dy in _NEIGH:
            nx, ny = x + dx, y + dy
            if not field.in_bounds(nx, ny):
                continue
            if (nx, ny) in dist:
                continue
            # walls block the field; rubble/grass conduct it
            if field.is_blocking(nx, ny):
                continue
            dist[(nx, ny)] = d + 1
            q.append((nx, ny))
    return dist


def step_down(field, x: int, y: int,
              dist: Dict[Tuple[int, int], int]
              ) -> Optional[Tuple[int, int]]:
    """The adjacent free tile that gets closest to the target."""
    here = dist.get((x, y))
    best, best_d = None, here if here is not None else 10 ** 9
    for dx, dy in _NEIGH:
        nx, ny = x + dx, y + dy
        d = dist.get((nx, ny))
        if d is None:
            continue
        if d < best_d and field.passable(nx, ny):
            best, best_d = (nx, ny), d
    return best
