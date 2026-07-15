"""Facing & arcs (P17.11) — the geometry of flanking.

A soldier faces one of eight directions. A blow lands in his FRONT
arc (the 3 tiles he faces), a FLANK arc (the 2 side tiles), or his
REAR arc (the 3 tiles behind). Hitting a man who is looking the
other way — because he is busy fighting someone in front — is how
flanking and rear attacks win battles. This is pure geometry (no
field, no rng) so it is unit-tested directly; the bonuses it feeds
live in `battle_ai`.
"""

# the 8 compass directions, index 0..7 going counter-clockwise-ish
DIRS = [(1, 0), (1, 1), (0, 1), (-1, 1),
        (-1, 0), (-1, -1), (0, -1), (1, -1)]

# arc → (to-hit bonus, damage multiplier). Flank and (worse) rear
# hits are easier to land and hit harder.
ARC_TO_HIT = {"front": 0, "flank": 2, "rear": 4}
ARC_DMG = {"front": 1.0, "flank": 1.25, "rear": 1.5}


def dir_index(dx, dy):
    """The compass index (0..7) of a delta, or None for (0,0)."""
    sx = (dx > 0) - (dx < 0)
    sy = (dy > 0) - (dy < 0)
    if (sx, sy) == (0, 0):
        return None
    return DIRS.index((sx, sy))


def face_toward(fx, fy, tx, ty):
    """The unit facing vector pointing from (fx,fy) toward (tx,ty);
    defaults to (1,0) when they share a tile."""
    i = dir_index(tx - fx, ty - fy)
    return DIRS[i] if i is not None else (1, 0)


def arc(facing, attacker_pos, target_pos) -> str:
    """Which arc the attacker sits in, relative to the target's
    facing: 'front' | 'flank' | 'rear'."""
    fi = dir_index(*facing)
    hi = dir_index(attacker_pos[0] - target_pos[0],
                   attacker_pos[1] - target_pos[1])
    if fi is None or hi is None:
        return "front"
    diff = min((fi - hi) % 8, (hi - fi) % 8)     # 0..4 apart
    if diff <= 1:
        return "front"
    if diff == 2:
        return "flank"
    return "rear"
