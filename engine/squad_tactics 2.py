"""Squad tactics (P7.3) — fights read as coordinated, not queued.

Playtest 2: wolves converged but then waited in a line; companions hit
whatever was adjacent; guards approached single-file. Three positional
helpers fix all of it, shared by companions, guards (P7.1) and monster
packs alike — pure geometry, zero LLM:

- `surround_step`: approach the FREE tile adjacent to the target
  nearest to you, so multiple attackers fan out around a victim
  instead of stacking behind one another.
- `flank_tile`: the tile directly opposite the player across the
  target — standing there earns the existing +2 flanking bonus
  (combat_system._flanking_bonus). Falls back to any free adjacent
  tile.
- `player_focus_target`: the enemy the player last struck (recorded by
  combat_system.player_attack); companions prioritize it — focus fire.

`greedy_step` is the shared mover: one step toward a goal, sliding
along obstacles (other axis first, then perpendicular) rather than
stalling — the fix that killed the historic companion-follow flake.
"""

from typing import Optional, Tuple

FOCUS_RADIUS = 8      # companions join the player's fight this far out

_NEIGHBORS = ((1, 0), (-1, 0), (0, 1), (0, -1),
              (1, 1), (1, -1), (-1, 1), (-1, -1))


def _free(wmap, x: int, y: int) -> bool:
    if not (0 <= x < wmap.width and 0 <= y < wmap.height):
        return False
    try:
        if wmap.get_terrain_at(x, y).value in ("water", "mountain"):
            return False
        return wmap.get_character_at(x, y) is None
    except Exception:
        return False


def surround_step(wmap, attacker, target) -> Optional[Tuple[int, int]]:
    """The free tile adjacent to the target nearest the attacker."""
    ax, ay = attacker.position
    tx, ty = target.position
    best, best_d = None, 10 ** 6
    for dx, dy in _NEIGHBORS:
        x, y = tx + dx, ty + dy
        if (x, y) == (ax, ay):
            return (x, y)               # already in position
        if not _free(wmap, x, y):
            continue
        d = abs(x - ax) + abs(y - ay)
        if d < best_d:
            best, best_d = (x, y), d
    return best


def flank_tile(engine, ally, target) -> Optional[Tuple[int, int]]:
    """Adjacent tile opposite the player — the +2 flanking spot."""
    wmap = engine.world.map
    px, py = engine.player.position
    tx, ty = target.position
    ox = tx + max(-1, min(1, tx - px))
    oy = ty + max(-1, min(1, ty - py))
    if (ox, oy) != (tx, ty):
        if ally.position == (ox, oy) or _free(wmap, ox, oy):
            return (ox, oy)
    return surround_step(wmap, ally, target)


def player_focus_target(engine):
    """The hostile the player last struck, if it still stands."""
    tid = getattr(engine, "player_target_id", None)
    if not tid:
        return None
    target = engine.npc_manager.npcs.get(tid)
    if target is None or not target.is_active():
        return None
    return target


def path_step(wmap, char, goal: Tuple[int, int],
              max_nodes: int = 900) -> bool:
    """One step along a real BFS path (4-dir) to goal; falls back to
    greedy sliding when no path exists or the search grows too large.
    Companions use this — greedy movement traps in concave terrain."""
    from collections import deque
    start = tuple(char.position)
    goal = tuple(goal)
    if start == goal:
        return True
    seen = {start}
    queue = deque([(start, start)])   # (tile, first-step-taken)
    while queue and len(seen) <= max_nodes:
        (x, y), first = queue.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nxt = (x + dx, y + dy)
            if nxt in seen:
                continue
            seen.add(nxt)
            if nxt == goal or _free(wmap, *nxt):
                step = nxt if first == start else first
                if nxt == goal:
                    return wmap.move_character(char, *step)
                queue.append((nxt, step))
    return greedy_step(wmap, char, goal)


def greedy_step(wmap, char, goal: Tuple[int, int]) -> bool:
    """One step toward goal, sliding along obstacles when blocked."""
    cx, cy = char.position
    gx, gy = goal
    sx = (gx > cx) - (gx < cx)
    sy = (gy > cy) - (gy < cy)
    if not sx and not sy:
        return True
    dx, dy = sx, sy
    if dx and dy:
        if abs(gx - cx) > abs(gy - cy):
            dy = 0
        else:
            dx = 0
    if wmap.move_character(char, cx + dx, cy + dy):
        return True
    if (sx, sy) != (dx, dy) and \
            wmap.move_character(char, cx + sx - dx, cy + sy - dy):
        return True
    if dx:
        return wmap.move_character(char, cx, cy + 1) or \
            wmap.move_character(char, cx, cy - 1)
    return wmap.move_character(char, cx + 1, cy) or \
        wmap.move_character(char, cx - 1, cy)
