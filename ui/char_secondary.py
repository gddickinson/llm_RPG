"""P34.3 secondary motion — springs, follow-through & look-at (pure).

The puppet is stateless per frame; these helpers add the PERSISTENT inter-frame
state that makes a body feel alive: a critically-damped spring the head & weapon
lag behind on (follow-through / settle), and a look-at that eases the head + eyes
toward a point of interest. All pure math over small state tuples stored in
`metadata['_anim']['_sec']`; `body_renderer` integrates them each frame.
"""

import math

LOOK_MAX = 1.0            # look direction is unit; the pixel amount is set by H
HEAD_STIFF = 260.0        # head follow-through (stiff → subtle lag)
WEAP_STIFF = 150.0        # weapon tip lags more → a whippy swing


def spring2(x, y, vx, vy, tx, ty, dt, stiffness=220.0, damping=None):
    """One step of a critically-damped 2D spring toward (tx, ty). Returns the
    new (x, y, vx, vy). Lower stiffness = looser, wobblier, funnier."""
    if damping is None:
        damping = 2.0 * stiffness ** 0.5
    vx += (stiffness * (tx - x) - damping * vx) * dt
    vy += (stiffness * (ty - y) - damping * vy) * dt
    return x + vx * dt, y + vy * dt, vx, vy


def look_dir(from_pos, to_pos, cone_y=0.65):
    """A clamped unit-ish look direction from one tile toward another; the
    vertical is compressed (a believable cone). Returns (dx, dy) in [-1, 1]."""
    dx = to_pos[0] - from_pos[0]
    dy = to_pos[1] - from_pos[1]
    d = math.hypot(dx, dy) or 1.0
    return (max(-1.0, min(1.0, dx / d)),
            max(-1.0, min(1.0, dy / d * cone_y)))


def ease2(cur, want, k=0.15):
    """Exponential ease of a 2D value toward a target (a smooth turn)."""
    return (cur[0] + (want[0] - cur[0]) * k,
            cur[1] + (want[1] - cur[1]) * k)
