"""Battlefield elevation (P17.E1) — the advantage of high ground.

The terrain itself as a combatant. A tile carries an ELEVATION on the
field (`field.elevation_at`); this module reads the height difference
between two positions and turns it into the classic edge of the high
ground, all pure and testable:

  * DOWNHILL you strike easier — +1 to-hit per level you stand above
    your foe (capped); UPHILL costs you the same.
  * A charge DOWNHILL gathers momentum (more damage); UPHILL it stalls.
  * HEIGHT extends a bow's range and a lookout's sight — you shoot and
    see farther from a hill or a rampart.

Zero-cost on flat ground (the common case), so a battle with no
elevation set behaves exactly as before.
"""

MAX_TO_HIT = 3          # cap the height-of-advantage to-hit swing
MAX_REACH = 2           # cap the extra ranged tiles from height

# E2: obstacle terrain you can cross but only SLOWLY — a stream to wade,
# a ditch to scramble, a bog to slog. Cost is in movement budget per
# tile entered (1 = normal ground).
MOVE_COST = {"stream": 2, "ditch": 2, "bog": 3, "marsh": 2, "mud": 2}

# E3: terrain tall/dense enough to BLOCK sight — you can't loose an arrow
# through a treeline, a wall, or a hill. Low cover (hedge/sandbags) you
# shoot over; a forest you cannot see through.
SIGHT_BLOCK = ("wall", "gate", "mountain", "forest", "building",
               "cliff", "rampart")


def _diff(field, atk_pos, def_pos) -> int:
    return field.elevation_at(*atk_pos) - field.elevation_at(*def_pos)


def height_to_hit(field, atk_pos, def_pos) -> int:
    """+to-hit downhill, −to-hit uphill (capped) — the high-ground edge."""
    d = _diff(field, atk_pos, def_pos)
    return max(-MAX_TO_HIT, min(MAX_TO_HIT, d))


def charge_dmg_mult(field, atk_pos, def_pos) -> float:
    """A charge DOWNHILL hits harder (momentum); UPHILL it's blunted."""
    d = _diff(field, atk_pos, def_pos)
    if d > 0:
        return 1.0 + 0.15 * min(d, 2)          # up to +30%
    if d < 0:
        return max(0.6, 1.0 + 0.2 * d)          # down to −40%
    return 1.0


def height_reach(field, pos) -> int:
    """Extra ranged tiles (and sight) from standing high (P17.E1)."""
    return max(0, min(MAX_REACH, field.elevation_at(*pos)))


# ---- E2: obstacle terrain -------------------------------------------

def move_cost(field, x: int, y: int) -> float:
    """The movement budget it costs to ENTER a tile — wading a stream or
    slogging a bog spends more than crossing open ground (P17.E2)."""
    if not field.in_bounds(x, y):
        return 1.0
    return MOVE_COST.get(field.terrain[y][x], 1.0)


def anchored(field, atk_pos, def_pos, facing) -> bool:
    """True if the defender's flank/rear on the ATTACKER's side rests on
    impassable terrain (a river, cliff, moat, wall) — the anchor that
    cannot be turned, so a blow from that arc lands as if to the front
    (P17.E2: the first thing good deployment does)."""
    from engine.battle import battle_facing as bf_face
    ar = bf_face.arc(facing, atk_pos, def_pos)
    if ar == "front":
        return False
    fx, fy = facing
    dx, dy = def_pos
    if ar == "rear":
        side = (-fx, -fy)                      # your back to the wall
    else:                                       # the flank the attacker's on
        p1, p2 = (-fy, fx), (fy, -fx)
        vx, vy = atk_pos[0] - dx, atk_pos[1] - dy
        side = p1 if (p1[0] * vx + p1[1] * vy) >= \
            (p2[0] * vx + p2[1] * vy) else p2
    tx, ty = dx + side[0], dy + side[1]
    return field.in_bounds(tx, ty) and field.is_blocking(tx, ty)


# ---- E3: battle line-of-sight ---------------------------------------

def has_los(field, a, b) -> bool:
    """Can a shooter at `a` see (and so hit) `b`? Sight-blocking terrain
    on the line between them — a treeline, a wall, a ridge — hides the
    target (P17.E3). The shooter's own tile and the target's tile don't
    block, so an archer fires FROM the edge of a wood but not THROUGH it.

    A Bresenham line-walk (O(distance)) rather than a full FOV per shot —
    the same idea as `world/fov.overworld_los`, sized for a battle that
    checks LOS every tick per archer."""
    x0, y0 = a
    x1, y1 = b
    dx = abs(x1 - x0)
    dy = abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx - dy
    x, y = x0, y0
    while (x, y) != (x1, y1):
        e2 = 2 * err
        if e2 > -dy:
            err -= dy
            x += sx
        if e2 < dx:
            err += dx
            y += sy
        if (x, y) == (x1, y1):              # reached the target — endpoints
            break                           # never block their own line
        if field.in_bounds(x, y) and field.terrain[y][x] in SIGHT_BLOCK:
            return False
    return True
