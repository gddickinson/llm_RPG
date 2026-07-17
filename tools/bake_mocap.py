"""Bake Mixamo mocap cache clips into compact 2D keyframe clips for the puppet.

The movieMaker "pose cache" (`assets/mixamo/.pose_cache/<Clip>.json`) stores, per
clip: {fps, frames, bones:[65], rest:{bone: mat16}, anim:[frame{bone: mat16}]}.
CRUCIAL FORMAT FACT (learned by inspection + reading movieMaker's
`mm/cast/mixamo_rig.py`): every `mat16` is a flat, row-major 4x4 WORLD transform
(fbx, Z-up).  Because the anim frames are already WORLD matrices, no
forward-kinematics or quaternion math is required at all -- the world position of
a bone is simply the translation column `M[:3, 3]`.  We reuse movieMaker's exact
axis convention (`_ROT`: Z-up -> Y-up) so our mapping matches its rig verbatim.

Pipeline per clip:
  1. read the cache JSON directly (no pygltflib needed).
  2. for each frame, take the translation column of the 16 bones we need,
     convert Z-up -> Y-up (movieMaker `_ROT`).
  3. map the 16 bones -> our 15 puppet joints.
  4. SIDE-view projection: screen_x = forward axis (+Z converted), screen_y = up
     (+Y converted).  Forward root motion is removed by subtracting the hips'
     per-frame forward position so the cycle animates in place.
  5. normalize: divide by the rest foot->head span (standing height == 1.0),
     put the ground (lowest foot across the clip) at y == 0, up positive.
  6. downsample to K keyframes and write data/anim/<key>.json.

Run:  .venv/bin/python tools/bake_mocap.py
Deps: numpy (present in the RPG venv).  If numpy were missing we fall back to a
tiny pure-python matrix helper -- but positions only need the translation column,
so numpy is optional convenience here.
"""

from __future__ import annotations

import json
import math
import os

try:  # numpy is present in the RPG venv; degrade gracefully if not
    import numpy as np
    _HAVE_NP = True
except Exception:  # pragma: no cover - fallback path
    np = None
    _HAVE_NP = False

# --------------------------------------------------------------------------- IO
CACHE_DIR = "/Users/george/claude_test/movieMaker/assets/mixamo/.pose_cache"
OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "data", "anim")

# Z-up -> Y-up, verbatim from movieMaker mm/cast/mixamo_rig.py (_ROT).  After
# this, up = +Y and the mixamo rest faces +Z (its forward axis).
_ROT = ((1.0, 0.0, 0.0), (0.0, 0.0, 1.0), (0.0, -1.0, 0.0))

# forward = +Z(converted); the puppet mirrors for facing, so this is a convention
FORWARD_SIGN = 1.0

# our 15 puppet joints <- mixamo bones (bone ORIGIN = the joint point).
JOINT_BONE = {
    "l_hip": "mixamorig:LeftUpLeg",
    "r_hip": "mixamorig:RightUpLeg",
    "chest": "mixamorig:Spine2",
    "l_knee": "mixamorig:LeftLeg",
    "r_knee": "mixamorig:RightLeg",
    "l_foot": "mixamorig:LeftFoot",
    "r_foot": "mixamorig:RightFoot",
    "l_sh": "mixamorig:LeftArm",
    "r_sh": "mixamorig:RightArm",
    "neck": "mixamorig:Neck",
    "head": "mixamorig:Head",
    "l_elbow": "mixamorig:LeftForeArm",
    "l_hand": "mixamorig:LeftHand",
    "r_elbow": "mixamorig:RightForeArm",
    "r_hand": "mixamorig:RightHand",
}
JOINT_ORDER = ("l_hip", "r_hip", "chest", "l_knee", "r_knee", "l_foot", "r_foot",
               "l_sh", "r_sh", "neck", "head", "l_elbow", "l_hand", "r_elbow",
               "r_hand")
HIPS = "mixamorig:Hips"

# clip file (no .json) -> (output key, loop?, target keyframes)
CLIPS = [
    ("Walking", "walk", True, 16),
    ("Jogging", "run", True, 18),
    ("Big Jump", "jump", False, 20),
    ("Front Flip", "flip", False, 20),
    ("Sitting Idle", "sit", False, 16),
    ("Breathing Idle", "idle", True, 16),
    ("Talking-2", "talk", True, 18),
    ("Dancing", "dance", True, 24),
    ("Hip Hop Dancing", "hiphop", True, 24),
    ("Climbing Ladder", "climb", True, 16),
    ("Head Nod Yes", "nod", True, 16),
    ("Standing Arguing", "argue", True, 20),
    ("Drunk Walking Turn", "stagger", True, 20),
    ("Catwalk Walking", "catwalk", True, 18),
    ("Breakdance 1990", "breakdance", True, 24),
    ("Flying Knee Punch Combo", "kick", False, 20),
    ("Idle-2", "idle2", True, 16),
    ("Idle-3", "idle3", True, 16),
    # ISO.14 — more combat moves + gestures baked from Mixamo (George)
    ("Bouncing Fight Idle", "fight_idle", True, 18),
    ("Body Jab Cross", "jab", False, 18),
    ("Center Block", "block", False, 14),
    ("Charge", "charge", False, 18),
    ("Double Dagger Stab", "stab", False, 16),
    ("Acknowledging", "acknowledge", False, 16),
    ("Angry Point", "point", False, 16),
    ("Asking Question", "ask", False, 18),
    ("Beckoning", "beckon", False, 16),
    ("Bored", "bored", True, 20),
    ("Looking Around", "look", True, 20),
    ("Praying", "pray", True, 18),
    ("No", "no", False, 14),
    ("Silly Dancing", "silly", True, 24),
    # ISO.16 — real sword combat, a hit reaction, a cast, a death fall
    ("sword and shield attack", "sword_attack", False, 18),
    ("sword and shield attack 2", "sword_attack2", False, 18),
    ("sword and shield casting", "spellcast", False, 20),
    ("Hit To Body", "hit", False, 14),
    ("Flying Back Death", "die", False, 18),
]


# ---------------------------------------------------------------- math helpers
def _translation(mat16):
    """World position (fbx Z-up) = the translation column of a row-major 4x4."""
    # row-major flat: indices 3, 7, 11 are the translation column (x, y, z).
    return (mat16[3], mat16[7], mat16[11])


def _to_yup(t):
    """Apply movieMaker _ROT: Z-up (x,y,z) -> Y-up (x, up=+Y, fwd=+Z)."""
    x, y, z = t
    return (_ROT[0][0] * x + _ROT[0][1] * y + _ROT[0][2] * z,
            _ROT[1][0] * x + _ROT[1][1] * y + _ROT[1][2] * z,
            _ROT[2][0] * x + _ROT[2][1] * y + _ROT[2][2] * z)


def _bone_yup(frame, bone, rest):
    """Converted (x, up, fwd) for a bone in a frame, rest-filled if absent."""
    m = frame.get(bone) or rest.get(bone)
    return _to_yup(_translation(m))


# ------------------------------------------------------------------ downsample
def _key_indices(n_frames, k, loop):
    """K frame indices.  Loop clips exclude the wrap frame (N==0); one-shots
    include both endpoints."""
    k = max(2, min(k, n_frames))
    if loop:
        return [round(i * n_frames / k) % n_frames for i in range(k)]
    return sorted(set(round(i * (n_frames - 1) / (k - 1)) for i in range(k)))


# ------------------------------------------------------------------- the bake
def bake_clip(src_name, key, loop, target_keys):
    path = os.path.join(CACHE_DIR, src_name + ".json")
    if not os.path.exists(path):
        return None, f"cache file missing: {path}"
    dump = json.load(open(path))
    rest = dump["rest"]
    anim = dump["anim"]
    fps = dump.get("fps", 24)
    n = len(anim)

    # --- normalization reference: rest standing height (foot -> head, up axis)
    rest_head_up = _to_yup(_translation(rest["mixamorig:Head"]))[1]
    rest_lfoot_up = _to_yup(_translation(rest["mixamorig:LeftFoot"]))[1]
    rest_rfoot_up = _to_yup(_translation(rest["mixamorig:RightFoot"]))[1]
    rest_foot_up = 0.5 * (rest_lfoot_up + rest_rfoot_up)
    height = rest_head_up - rest_foot_up
    if abs(height) < 1e-9:
        return None, "degenerate rest height"

    # --- pass 1: raw converted positions for every frame + joint
    raw = []   # raw[f][joint] = (fwd, up)
    hip_fwd = []
    ground_up = math.inf
    for f in range(n):
        frame = anim[f]
        hx, hup, hfwd = _bone_yup(frame, HIPS, rest)
        hip_fwd.append(hfwd)
        jp = {}
        for j in JOINT_ORDER:
            _x, up, fwd = _bone_yup(frame, JOINT_BONE[j], rest)
            jp[j] = (fwd, up)
            if j in ("l_foot", "r_foot"):
                ground_up = min(ground_up, up)
        raw.append(jp)

    # --- pass 2: normalize (feet ground -> 0, /height; remove fwd root motion)
    def norm(joint_fp, f):
        fwd, up = joint_fp
        x = FORWARD_SIGN * (fwd - hip_fwd[f]) / height
        y = (up - ground_up) / height
        return [round(x, 5), round(y, 5)]

    idxs = _key_indices(n, target_keys, loop)
    joints_out = {j: [] for j in JOINT_ORDER}
    for f in idxs:
        for j in JOINT_ORDER:
            joints_out[j].append(norm(raw[f][j], f))

    clip = {"clip": key, "fps": fps, "loop": bool(loop), "keys": len(idxs),
            "joints": joints_out}
    return clip, None


# --------------------------------------------------------------- verification
def _series(clip, joint, axis):
    return [p[axis] for p in clip["joints"][joint]]


def _corr(a, b):
    if _HAVE_NP:
        a = np.asarray(a); b = np.asarray(b)
        if a.std() < 1e-9 or b.std() < 1e-9:
            return 0.0
        return float(np.corrcoef(a, b)[0, 1])
    n = len(a)
    ma, mb = sum(a) / n, sum(b) / n
    va = sum((x - ma) ** 2 for x in a); vb = sum((x - mb) ** 2 for x in b)
    if va < 1e-12 or vb < 1e-12:
        return 0.0
    cov = sum((a[i] - ma) * (b[i] - mb) for i in range(n))
    return cov / math.sqrt(va * vb)


def sanity(clip):
    ys = [p[1] for j in JOINT_ORDER for p in clip["joints"][j]]
    span = max(ys) - min(ys)
    head_y = _series(clip, "head", 1)
    lf_y = _series(clip, "l_foot", 1)
    rf_y = _series(clip, "r_foot", 1)
    min_foot = min(min(lf_y), min(rf_y))
    foot_phase = _corr(_series(clip, "l_foot", 0), _series(clip, "r_foot", 0))
    return {
        "keys": clip["keys"],
        "height_span": round(span, 3),
        "head_y_range": (round(min(head_y), 3), round(max(head_y), 3)),
        "min_foot_y": round(min_foot, 3),
        "foot_phase_corr": round(foot_phase, 3),
    }


# --------------------------------------------------------------------- driver
def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    print(f"baking -> {OUT_DIR}\n")
    print(f"{'clip':11s} {'keys':>4s} {'span':>5s} {'head_y range':>14s} "
          f"{'minFoot':>7s} {'footPhase':>9s}  notes")
    print("-" * 78)
    ok, failed = [], []
    for src, key, loop, nk in CLIPS:
        clip, err = bake_clip(src, key, loop, nk)
        if clip is None:
            failed.append((key, err))
            print(f"{key:11s}  FAILED: {err}")
            continue
        with open(os.path.join(OUT_DIR, key + ".json"), "w") as fh:
            json.dump(clip, fh, separators=(",", ":"))
        s = sanity(clip)
        note = ""
        if key == "walk":
            note = "ANTIPHASE ok" if s["foot_phase_corr"] < -0.3 else "!! phase"
            if not (0.85 <= s["head_y_range"][1] <= 1.05):
                note += " !!head"
        loopstr = "loop" if loop else "once"
        print(f"{key:11s} {s['keys']:>4d} {s['height_span']:>5.2f} "
              f"{str(s['head_y_range']):>14s} {s['min_foot_y']:>7.2f} "
              f"{s['foot_phase_corr']:>9.2f}  {loopstr} {note}")
        ok.append((key, s))
    print("-" * 78)
    print(f"\nbaked {len(ok)} clips, {len(failed)} failed")
    for key, err in failed:
        print(f"  FAILED {key}: {err}")


if __name__ == "__main__":
    main()
