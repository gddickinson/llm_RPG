"""Shared primitives for the procedural clip library (P34.10 split).

`char_clips` (core clips) and `char_clips_more` (the expanded acrobatics / daily-
life library) both build on these pure joint helpers, so the vocabulary lives in
ONE place. No pygame; headless-testable.
"""

import math

from ui.char_pose import scale_pose            # re-exported for the clip modules

# the 15-joint skeleton, and the "upper body" subset the clips lean on
_JOINTS = ["l_hip", "r_hip", "chest", "l_knee", "r_knee", "l_foot", "r_foot",
           "l_sh", "r_sh", "neck", "head", "l_elbow", "l_hand",
           "r_elbow", "r_hand"]
_UPPER = ["chest", "l_sh", "r_sh", "neck", "head",
          "l_elbow", "l_hand", "r_elbow", "r_hand"]

__all__ = ["math", "scale_pose", "_JOINTS", "_UPPER", "_arc", "_ease", "_fdir",
           "_move", "_feet_pivot", "_centroid", "_rotate", "_swing"]


def _arc(t):                      # 0 → 1 → 0 over t in [0, 1] (a there-and-back)
    return math.sin(max(0.0, min(1.0, t)) * math.pi)


def _ease(t):                     # smoothstep 0 → 1 (monotonic)
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def _fdir(facing):
    return facing[0] if facing[0] else 0


def _move(pose, keys, dx, dy):
    for k in keys:
        if k in pose:
            pose[k] = (pose[k][0] + dx, pose[k][1] + dy)


def _feet_pivot(pose):
    return ((pose["l_foot"][0] + pose["r_foot"][0]) / 2,
            max(pose["l_foot"][1], pose["r_foot"][1]))


def _centroid(pose):
    xs = [pose[k][0] for k in _JOINTS if k in pose]
    ys = [pose[k][1] for k in _JOINTS if k in pose]
    return (sum(xs) / len(xs), sum(ys) / len(ys))


def _rotate(pose, keys, cx, cy, ang):
    """Rotate `keys` about (cx, cy) by `ang` radians — the engine behind flips,
    rolls and cartwheels (a whole-body spin the 2D puppet otherwise can't do)."""
    ca, sa = math.cos(ang), math.sin(ang)
    for k in keys:
        if k in pose:
            x, y = pose[k]
            dx, dy = x - cx, y - cy
            pose[k] = (cx + dx * ca - dy * sa, cy + dx * sa + dy * ca)


def _swing(pose, hand, sh, el, ang, reach):
    """Place a hand at angle `ang` (rad, 0 = down) a `reach` from its shoulder,
    elbow at the midpoint — the shared arm-poser for waves, thrusts and reaches."""
    s = pose[sh]
    hx, hy = s[0] + reach * math.sin(ang), s[1] + reach * math.cos(ang)
    pose[hand] = (hx, hy)
    pose[el] = ((s[0] + hx) / 2, (s[1] + hy) / 2)
