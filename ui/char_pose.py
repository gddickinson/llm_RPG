"""P33.4b/6a character pose — the pure skeleton math behind the detailed body.

Given the animation state (walk / idle phase, attack progress, facing) and a
foot anchor + pixel height, compute the screen position of every joint so
`body_renderer` just draws limbs between the points. FOUR facings: FRONT, BACK
(no face), and a SIDE PROFILE for left/right (edge-on, limbs striding fore-aft).
A per-character BUILD (P33.6a) scales shoulder/hip width, head size and girth so
the cast is diverse and a touch cartoonish. All headless-testable.

Coordinates are screen pixels, y DOWN; the character is anchored at the feet
(`foot_y`) and rises `H` pixels — taller than one tile, so it reads big.
"""

import math

KNEE, HIP, CHEST, SHOULDER, NECK, HEAD_C = 0.26, 0.49, 0.66, 0.74, 0.77, 0.88
HEAD_R = 0.145                 # P33.6a: a bigger, rounder, cartoonish head
SHOULDER_W, HIP_W = 0.34, 0.24

_DEFAULT_BUILD = {"shoulder": 1.0, "hip": 1.0, "head": 1.0, "girth": 1.0}


def _ease(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


_JOINT_KEYS = ("l_hip", "r_hip", "chest", "l_knee", "r_knee", "l_foot",
               "r_foot", "l_sh", "r_sh", "neck", "head", "l_elbow", "l_hand",
               "r_elbow", "r_hand")


def scale_pose(pose, sx, sy, pivot):
    """P34.1 squash & stretch — scale every joint about `pivot` (usually the
    feet). sx>1,sy<1 squashes (wider, shorter); sx<1,sy>1 stretches. Preserves
    volume when sx*sy≈1. Mutates + returns the pose."""
    px, py = pivot
    for k in _JOINT_KEYS:
        if k in pose:
            x, y = pose[k]
            pose[k] = (px + (x - px) * sx, py + (y - py) * sy)
    return pose


def _attack_angle(p):
    """P34.1 anticipation: a slow wind-up PAST neutral, a fast strike, then a
    settling recovery — timing contrast sells the blow. Degrees from vertical."""
    if p < 0.30:
        return -45 - 40 * _ease(p / 0.30)              # pull back (slow)
    if p < 0.58:
        return -85 + 205 * _ease((p - 0.30) / 0.28)    # strike (fast)
    return 120 - 30 * _ease((p - 0.58) / 0.42)         # recover (settle)


def weapon_dir(facing):
    fx, fy = facing
    if fx:
        return 1 if fx > 0 else -1
    return 0 if fy < 0 else 1


def build_pose(cx, foot_y, H, walk=0.0, idle=0.0, moving=False,
               attack=0.0, facing=(0, 1), build=None):
    b = build or _DEFAULT_BUILD
    fx, _fy = facing
    if fx:
        return _side_pose(cx, foot_y, H, walk, idle, moving, attack,
                          1 if fx > 0 else -1, b)
    return _front_pose(cx, foot_y, H, walk, idle, moving, attack, facing, b)


def _bob_breath(H, walk, idle, moving):
    return (-abs(math.sin(walk)) * H * 0.045 if moving else 0.0,
            0.0 if moving else math.sin(idle) * H * 0.012)


def _front_pose(cx, foot_y, H, walk, idle, moving, attack, facing, b):
    sw = math.sin(walk)
    bob, breath = _bob_breath(H, walk, idle, moving)

    def yy(f):
        return foot_y - f * H + bob

    hipw, shw = H * HIP_W * b["hip"], H * SHOULDER_W * b["shoulder"]
    stride = H * 0.12 if moving else 0.0
    lift = H * 0.055
    l_hip = (cx - hipw / 2, yy(HIP))
    r_hip = (cx + hipw / 2, yy(HIP))
    l_foot = (cx - hipw / 2 + sw * stride, foot_y - max(0.0, sw) * lift)
    r_foot = (cx + hipw / 2 - sw * stride, foot_y - max(0.0, -sw) * lift)
    bend = H * 0.05
    l_knee = ((l_hip[0] + l_foot[0]) / 2 + (sw > 0) * bend, yy(KNEE))
    r_knee = ((r_hip[0] + r_foot[0]) / 2 + (sw < 0) * bend, yy(KNEE))
    l_sh = (cx - shw / 2, yy(SHOULDER) - breath)
    r_sh = (cx + shw / 2, yy(SHOULDER) - breath)
    arm = H * 0.30
    asw = -sw * H * 0.09
    l_hand = (l_sh[0] - H * 0.02 + asw, l_sh[1] + arm)
    l_elbow = ((l_sh[0] + l_hand[0]) / 2 - H * 0.03, l_sh[1] + arm * 0.5)
    fdir = weapon_dir(facing)
    if attack > 0.001:
        a = math.radians(_attack_angle(attack))
        r_hand = (r_sh[0] + arm * math.sin(a) * (fdir or 1),
                  r_sh[1] - arm * math.cos(a))
    else:
        r_hand = (r_sh[0] + H * 0.02 - asw, r_sh[1] + arm)
    r_elbow = ((r_sh[0] + r_hand[0]) / 2 + H * 0.03, (r_sh[1] + r_hand[1]) / 2)
    return _pack(cx, yy, breath, l_hip, r_hip, l_knee, r_knee, l_foot, r_foot,
                 l_sh, r_sh, l_elbow, l_hand, r_elbow, r_hand, H, facing, fdir,
                 0, 0.0, b)


def _side_pose(cx, foot_y, H, walk, idle, moving, attack, d, b):
    sw = math.sin(walk)
    bob, breath = _bob_breath(H, walk, idle, moving)

    def yy(f):
        return foot_y - f * H + bob

    stride = H * 0.18 if moving else H * 0.05
    lift = H * 0.06
    l_hip = (cx - d * H * 0.02, yy(HIP))
    r_hip = (cx + d * H * 0.02, yy(HIP))
    l_foot = (cx - d * sw * stride, foot_y - max(0.0, -sw) * lift)
    r_foot = (cx + d * sw * stride, foot_y - max(0.0, sw) * lift)
    l_knee = (cx - d * sw * stride * 0.5, yy(KNEE))
    r_knee = (cx + d * sw * stride * 0.5 + d * H * 0.02, yy(KNEE))
    l_sh = (cx - d * H * 0.03, yy(SHOULDER) - breath)
    r_sh = (cx + d * H * 0.03, yy(SHOULDER) - breath)
    arm = H * 0.30
    asw = sw * H * 0.10
    l_hand = (cx - d * (H * 0.04 + asw), l_sh[1] + arm * 0.85)
    l_elbow = ((l_sh[0] + l_hand[0]) / 2 - d * H * 0.02, l_sh[1] + arm * 0.45)
    if attack > 0.001:
        a = math.radians(_attack_angle(attack))
        r_hand = (r_sh[0] + d * arm * math.sin(a), r_sh[1] - arm * math.cos(a))
    else:
        r_hand = (r_sh[0] + d * (H * 0.13 + asw), r_sh[1] + arm * 0.6)
    r_elbow = ((r_sh[0] + r_hand[0]) / 2 + d * H * 0.02,
               (r_sh[1] + r_hand[1]) / 2)
    return _pack(cx, yy, breath, l_hip, r_hip, l_knee, r_knee, l_foot, r_foot,
                 l_sh, r_sh, l_elbow, l_hand, r_elbow, r_hand, H, (d, 0), d, d,
                 d * H * 0.045, b)


def _pack(cx, yy, breath, l_hip, r_hip, l_knee, r_knee, l_foot, r_foot,
          l_sh, r_sh, l_elbow, l_hand, r_elbow, r_hand, H, facing, fdir,
          profile, head_dx, b):
    return {
        "l_hip": l_hip, "r_hip": r_hip,
        "chest": (cx, yy(CHEST) - breath),
        "l_knee": l_knee, "r_knee": r_knee, "l_foot": l_foot, "r_foot": r_foot,
        "l_sh": l_sh, "r_sh": r_sh,
        "neck": (cx, yy(NECK) - breath),
        "head": (cx + head_dx, yy(HEAD_C) - breath),
        "head_r": max(2, int(H * HEAD_R * b["head"])),
        "l_elbow": l_elbow, "l_hand": l_hand,
        "r_elbow": r_elbow, "r_hand": r_hand,
        "facing": facing, "fdir": fdir, "profile": profile,
        "girth": b["girth"], "H": H,
    }
