"""P34.14 (proof of concept) — a 3D-body-coordinate pose for CONTINUOUS facing.

The existing `char_pose` hand-authors two views (front/back + side). This shows the
alternative that gives the cast full turn-in-any-direction motion in the 2.5D game:
give every joint BODY coordinates (u = across the shoulders, w = fore-aft DEPTH, y =
height) and PROJECT to the screen by the facing angle θ —

    screen_x = cx + (u·cosθ + w·sinθ)·H     screen_y = foot_y − y·H

θ=0 faces the camera (front), 90° faces screen-right (profile), 180° is the back.
The walk strides the legs in DEPTH (w), so at θ=0 the legs only lift (a front walk)
and at θ=90 they swing fore-aft (a side walk) — the SAME data, any angle between.
`cam_depth` (per joint) is the into-screen axis for depth-sorting the near/far limbs.
Pure + headless; drives the same body_parts draw as `char_pose`.
"""

import math

KNEE, HIP, CHEST, SH, NECK, HEAD = 0.26, 0.49, 0.66, 0.74, 0.77, 0.88
HEAD_R = 0.145
SHW, HIPW = 0.17, 0.10           # half-widths across the body (u)
ARM = 0.02

_JOINTS = ("l_hip", "r_hip", "chest", "l_knee", "r_knee", "l_foot", "r_foot",
           "l_sh", "r_sh", "neck", "head", "l_elbow", "l_hand", "r_elbow",
           "r_hand")


_NEUTRAL_GAIT = {"stride": 1.0, "bob": 1.0, "arm": 1.0, "cadence": 1.0}
_FEET = ("l_foot", "r_foot")
_SPINE_F = {"chest": 0.3, "l_sh": 0.45, "r_sh": 0.45, "neck": 0.6, "head": 0.9}
# lateral (u) rest position of each joint — supplied to the side-view mocap, which
# has no left/right info, so a projected mocap walk strides in DEPTH at any facing
_REST_U = {"l_hip": -HIPW, "r_hip": HIPW, "l_knee": -HIPW, "r_knee": HIPW,
           "l_foot": -HIPW, "r_foot": HIPW, "l_sh": -SHW, "r_sh": SHW,
           "chest": 0.0, "neck": 0.0, "head": 0.0,
           "l_elbow": -SHW - ARM, "r_elbow": SHW + ARM,
           "l_hand": -SHW - ARM, "r_hand": SHW + ARM}


def _wide(k, b):
    if "sh" in k or "hand" in k or "elbow" in k:
        return b["shoulder"]
    if "hip" in k or "knee" in k or "foot" in k:
        return b["hip"]
    return 1.0


def pose3d_mocap(cx, foot_y, H, clip, phase, facing_deg, build=None, gait=None,
                 spine=0.0):
    """Project a baked MOCAP clip through the depth model (P34.15): the mocap's
    side-view fore-aft (nx) becomes the DEPTH `w`, its height (ny) the y, and the
    lateral `u` comes from the rest skeleton — so real Mixamo stride/timing plays at
    ANY facing angle. Returns None if the clip is missing."""
    from ui import char_mocap
    norm = char_mocap.sample_norm(clip, phase)
    if norm is None:
        return None
    b = build or {"shoulder": 1.0, "hip": 1.0, "head": 1.0, "girth": 1.0}
    g = gait or _NEUTRAL_GAIT
    th = math.radians(facing_deg)
    c, s = math.cos(th), math.sin(th)
    root = (norm["l_hip"][0] + norm["r_hip"][0]) / 2.0    # centre the fore-aft
    pose, depth = {}, {}
    for k, (nx, ny) in norm.items():
        u = _REST_U.get(k, 0.0) * _wide(k, b)
        w = (nx - root) * g["stride"] + spine * _SPINE_F.get(k, 0.0)
        pose[k] = (cx + (u * c + w * s) * H, foot_y - ny * H)
        depth[k] = -u * s + w * c
    pose["head_r"] = max(2, int(H * HEAD_R * b["head"]))
    pose["profile"] = 1 if s > 0.35 else -1 if s < -0.35 else 0
    pose["fdir"] = pose["profile"]
    pose["facing"] = (pose["fdir"], 0)
    pose["girth"] = b.get("girth", 1.0)
    pose["H"] = H
    pose["cam_depth"] = depth
    pose["face_visible"] = c > -0.2
    return pose


def _body_coords(walk, moving, g):
    """Rest skeleton in (u, w, y) with a fore-aft (DEPTH) walk stride."""
    sw = math.sin(walk)
    stride = 0.17 * g["stride"] if moving else 0.0
    lift = 0.06
    asw = -sw * 0.15 * g["arm"]                         # arms counter-swing
    return {
        "l_hip": (-HIPW, 0.0, HIP), "r_hip": (HIPW, 0.0, HIP),
        "chest": (0.0, 0.0, CHEST), "neck": (0.0, 0.0, NECK),
        "head": (0.0, 0.0, HEAD),
        "l_sh": (-SHW, 0.0, SH), "r_sh": (SHW, 0.0, SH),
        "l_knee": (-HIPW, sw * stride * 0.5, KNEE),
        "r_knee": (HIPW, -sw * stride * 0.5, KNEE),
        "l_foot": (-HIPW, sw * stride, max(0.0, sw) * lift),
        "r_foot": (HIPW, -sw * stride, max(0.0, -sw) * lift),
        "l_elbow": (-SHW - ARM, asw * 0.5, 0.58),
        "l_hand": (-SHW - ARM, asw, 0.44),
        "r_elbow": (SHW + ARM, -asw * 0.5, 0.58),
        "r_hand": (SHW + ARM, -asw, 0.44),
    }


# P34.6 line-of-action: a mood → spine-curve (fore-aft, + = slump, − = proud arch)
_SPINE = {"sad": 0.10, "hurt": 0.11, "scared": 0.07, "happy": -0.05,
          "laughing": -0.06, "angry": -0.04, "surprised": -0.03}


def spine_for(mood):
    return _SPINE.get(mood, 0.0)


def pose3d(cx, foot_y, H, walk=0.0, facing_deg=0.0, build=None, moving=True,
           attack=0.0, attack_style="overhead", gait=None, idle=0.0, spine=0.0):
    """Project the body skeleton at facing angle `facing_deg` to a screen pose —
    a full drop-in for `char_pose.build_pose` (walk stride, gait, bob, attack, and a
    mood spine curve)."""
    b = build or {"shoulder": 1.0, "hip": 1.0, "head": 1.0, "girth": 1.0}
    g = gait or _NEUTRAL_GAIT
    th = math.radians(facing_deg)
    c, s = math.cos(th), math.sin(th)
    j = _body_coords(walk, moving, g)
    if spine:                          # bend the upper body along a C-curve (depth)
        for k, f in _SPINE_F.items():
            u, w, y = j[k]
            j[k] = (u, w + spine * f, y)
    # a vertical bob while striding, a gentle breath while still (feet stay down)
    bob = (-abs(math.sin(walk)) * H * 0.045 * g["bob"] if moving
           else math.sin(idle) * H * 0.012)
    pose, depth = {}, {}
    for k, (u, w, y) in j.items():
        wide = b["shoulder"] if ("sh" in k or "hand" in k or "elbow" in k) \
            else b["hip"] if ("hip" in k or "knee" in k or "foot" in k) else 1.0
        u *= wide
        yb = 0.0 if k in _FEET else bob
        pose[k] = (cx + (u * c + w * s) * H, foot_y - y * H + yb)
        depth[k] = -u * s + w * c                       # + = nearer the camera
    if attack > 0.001:                                  # a strike, projected
        from ui.char_pose import _attack_hand
        sign = 1 if s >= 0 else -1
        pose["r_hand"] = _attack_hand(attack_style, attack, pose["r_sh"],
                                      H * 0.36, sign, H)      # G3: a bolder reach
        pose["r_elbow"] = ((pose["r_sh"][0] + pose["r_hand"][0]) / 2,
                           (pose["r_sh"][1] + pose["r_hand"][1]) / 2)
    pose["head_r"] = max(2, int(H * HEAD_R * b["head"]))
    pose["profile"] = 1 if s > 0.35 else -1 if s < -0.35 else 0
    pose["fdir"] = pose["profile"]
    pose["facing"] = (pose["fdir"], 0)
    pose["girth"] = b.get("girth", 1.0)
    pose["H"] = H
    pose["cam_depth"] = depth
    pose["face_visible"] = c > -0.2                      # face shows unless ~back
    return pose


def facing_from_delta(dx, dy):
    """Movement heading → a facing angle (0 south/front toward camera)."""
    return math.degrees(math.atan2(dx, dy)) % 360.0
