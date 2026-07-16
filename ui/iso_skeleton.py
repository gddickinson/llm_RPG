"""ISO.6 — a rigged SKELETON driven by MIXAMO mocap for the iso characters.

George: "make the iso characters even more realistic using a rigged skeleton and
mixamo animations." The game already ships 18 Mixamo clips (`data/anim/*.json`,
baked by `tools/bake_mocap.py`) as 15-joint 2D SIDE-VIEW keyframes, sampled by
`char_mocap.sample_norm(clip, phase)`. This lifts that into 3D: each joint's
`(nx, ny)` becomes (fore-aft depth `z`, height `y`), the left/right joints are
spread laterally for body WIDTH, and a BONE (a box aligned along the segment via
`_bone`) is laid between every connected joint — legs (hip→knee→foot), spine
(pelvis→chest→neck), clavicles + arms (shoulder→elbow→hand), plus a head + hair.
So the figure is a real jointed skeleton animated by real mocap — natural gait,
knee-bend, arm-swing, weight — baked per phase like the rest of the iso world.
"""

import math

import numpy as np

from ui import char_mocap as cm
from ui import raster3d as r3

_H = 1.62                       # figure height (feet→head)
_D = 1.2                        # fore-aft depth scale
_HIP_W = 0.11                   # lateral half-width, hips/legs
_SH_W = 0.17                    # lateral half-width, shoulders/arms
_SKIN = (232, 196, 160)
_LEG = (56, 52, 64)

# the game action → the mocap clip that reads it
_CLIP = {"idle": "idle", "walk": "walk", "run": "run", "attack": "kick"}

# a camera framing the ~1.6-unit skeleton (tuned in the ISO.6 prototype)
CAM = dict(cam_pos=(2.1, 2.5, -2.5), look=(0.0, 0.78, 0.0), vfov_deg=30.0)

_LEGJ = ("_hip", "_knee", "_foot")
_ARMJ = ("_sh", "_elbow", "_hand")


def clip_for(action: str) -> str:
    return _CLIP.get(action, "idle")


def _lat(j: str) -> float:
    if j[:2] in ("l_", "r_"):
        side = -1.0 if j.startswith("l_") else 1.0
        if any(j.endswith(s) for s in _LEGJ):
            return side * _HIP_W
        if any(j.endswith(s) for s in _ARMJ):
            return side * _SH_W
    return 0.0


def pose3d(pose_norm, facing) -> dict:
    """{joint: (x,y,z)} — lateral spread + height + fore-aft depth, rotated to
    the 4-dir facing."""
    out = {j: np.array([_lat(j), ny * _H, nx * _D])
           for j, (nx, ny) in pose_norm.items()}
    out["pelvis"] = (out["l_hip"] + out["r_hip"]) / 2.0
    a = (facing % 4) * (math.pi / 2)
    c, s = math.cos(a), math.sin(a)
    rot = np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])
    return {k: rot @ v for k, v in out.items()}


def _bone(a, b, r, color):
    """A box of half-thickness `r` laid along the segment a→b (a limb)."""
    a = np.asarray(a, float)
    b = np.asarray(b, float)
    axis = b - a
    L = np.linalg.norm(axis) or 1e-6
    d = axis / L
    up = np.array([0, 0, 1.0]) if abs(d[1]) > 0.9 else np.array([0, 1.0, 0])
    p1 = np.cross(d, up)
    p1 = p1 / (np.linalg.norm(p1) or 1.0)
    p2 = np.cross(d, p1)
    cs = [a + sx * r * p1 + sy * r * p2 for sx in (-1, 1) for sy in (-1, 1)] \
        + [b + sx * r * p1 + sy * r * p2 for sx in (-1, 1) for sy in (-1, 1)]
    v = np.array(cs)
    t = np.array([[0, 1, 3], [0, 3, 2], [4, 7, 5], [4, 6, 7],
                  [0, 4, 5], [0, 5, 1], [1, 5, 7], [1, 7, 3],
                  [3, 7, 6], [3, 6, 2], [2, 6, 4], [2, 4, 0]])
    return v, t, tuple(int(x) for x in color)


def figure(pose_norm, tint, hair, facing):
    """Build the rigged bone-skeleton mesh from a sampled mocap pose."""
    P = pose3d(pose_norm, facing)
    dark = tuple(int(v * 0.82) for v in tint)
    m = []
    for side in ("l_", "r_"):
        m.append(_bone(P[side + "hip"], P[side + "knee"], 0.075, _LEG))
        m.append(_bone(P[side + "knee"], P[side + "foot"], 0.06, _LEG))
        f = P[side + "foot"]
        m.append(r3.box(f[0], f[1] - 0.02, f[2] + 0.05, 0.11, 0.05, 0.17, _LEG))
    m.append(_bone(P["pelvis"], P["chest"], 0.15, tint))
    m.append(_bone(P["chest"], P["neck"], 0.10, tint))
    m.append(_bone(P["chest"], P["l_sh"], 0.06, tint))
    m.append(_bone(P["chest"], P["r_sh"], 0.06, tint))
    for side in ("l_", "r_"):
        m.append(_bone(P[side + "sh"], P[side + "elbow"], 0.055, dark))
        m.append(_bone(P[side + "elbow"], P[side + "hand"], 0.045, dark))
    h = P["head"]
    m.append(r3.box(h[0], h[1] - 0.11, h[2], 0.22, 0.24, 0.22, _SKIN))
    m.append(r3.box(h[0], h[1] + 0.11, h[2], 0.24, 0.09, 0.24,
                    tuple(int(x) for x in hair)))
    return m


def sample_figure(action, phase, tint, hair, facing):
    """The skeleton mesh for `action` at `phase`, or None if the clip is
    missing (caller falls back to the box figure)."""
    pose = cm.sample_norm(clip_for(action), phase)
    if pose is None:
        return None
    try:
        return figure(pose, tint, hair, facing)
    except Exception:
        return None
