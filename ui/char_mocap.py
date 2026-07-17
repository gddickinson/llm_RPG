"""P34.8 mocap-driven clips — play baked Mixamo motion on the puppet.

`data/anim/<clip>.json` holds a real Mixamo mocap clip baked to a SIDE-VIEW 2D
skeleton (`tools/bake_mocap.py`): 15 joints, per-keyframe [x, y] normalized so the
feet rest at y≈0, the head at y≈1, and forward = +x. This module maps those
keyframes onto our screen puppet (feet-anchored, mirrored by facing) with keyframe
interpolation — giving mocap-quality timing/arcs for the SIDE facing. Pure + cached;
`body_renderer` uses a mocap clip when the character faces sideways and one exists,
falling back to the hand-authored `char_pose`/`char_clips` otherwise.
"""

import json
import os

_CACHE = {}
_JOINTS = ("l_hip", "r_hip", "chest", "l_knee", "r_knee", "l_foot", "r_foot",
           "l_sh", "r_sh", "neck", "head", "l_elbow", "l_hand", "r_elbow",
           "r_hand")

# our action -> baked clip name (only where a good mocap exists).
# NOTE: jump/leap deliberately fall through to the hand-authored char_clips._jump
# — the baked "jump" bake is an acrobatic FLIP (hips-over-head, head to the floor)
# that reads as a face-plant for a plain hop; the clean squash→launch→land clip is
# the right default for the player's jump key (P34.9). The flip bake stays available
# for a deliberate "flip" action.
ACTION_CLIP = {
    "walk": "walk", "run": "run", "flip": "jump",
    "sit": "sit", "sleep": "sit", "dance": "dance", "climb": "climb",
    "idle": "idle", "talk": "talk", "wave": "talk", "stagger": "stagger",
    # COMBAT.1 the 2D renderer plays the real combat + defence mocap too
    "block": "shield_block", "crouch_block": "crouch_block", "dodge": "roll",
    "hit": "hit", "hurt": "hit", "hit_head": "hit_head", "hit_back": "hit_back",
    "hit_legs": "hit_legs", "kick": "kick", "stab": "stab", "jab": "jab",
    "hook": "hook", "lead_jab": "lead_jab", "elbow": "elbow",
    "spellcast": "spellcast", "cast": "spellcast", "charge": "charge",
    "die": "die",
}


# COMBAT.1 the attack repertoire a fighter rotates through per strike (`seq`),
# by weapon — shared with the iso path's pools.
_BLADE = ("sword_attack", "sword_attack2", "sword_attack3", "sword_attack4",
          "sword_slash")
_FIST = ("jab", "hook", "lead_jab", "elbow")


def attack_clip(weapon, seq):
    """The melee-attack mocap clip for a weapon at strike `seq` (rotates the
    repertoire), or None for a polearm (→ the procedural swing)."""
    if weapon == "dagger":
        name = "stab"
    elif not weapon:
        name = _FIST[seq % len(_FIST)]
    elif weapon in ("sword", "axe", "mace"):
        name = _BLADE[seq % len(_BLADE)]
    else:
        return None
    return name if _load(name) else None


# the actions the 2D renderer plays from real combat mocap (not procedural)
_COMBAT = frozenset({
    "attack", "block", "crouch_block", "dodge", "roll", "hit", "hurt",
    "hit_head", "hit_back", "hit_legs", "kick", "stab", "jab", "hook",
    "lead_jab", "elbow", "spellcast", "cast", "charge", "die"})


def combat_mocap(action, anim, weapon, attack_progress):
    """(clip, phase) for a 2D COMBAT action, or None if it isn't one. An ATTACK
    rotates the weapon's repertoire by strike seq (phase = the strike progress);
    a one-shot block/dodge/hit plays 0→1 over its duration; a guard idle loops."""
    if action not in _COMBAT:
        return None
    anim = anim or {}
    if action == "attack":
        clip = attack_clip(weapon, int(anim.get("atk_seen", 0) or 0))
        return (clip, attack_progress) if clip else None
    clip = clip_for(action)
    if not clip:
        return None
    if is_loop(clip):
        return clip, anim.get("clock", 0.0) * 0.9
    dur = anim.get("action_dur")
    return clip, ((1.0 - anim.get("action_t", 0.0) / dur) if dur
                  else anim.get("clock", 0.0))
# cycle rate (loops/sec) driving a looping clip off the anim clock
RATE = {"walk": 2.6, "run": 3.6, "idle": 0.45, "talk": 0.8, "dance": 1.1,
        "climb": 1.4, "stagger": 2.0}


def _load(name):
    if name not in _CACHE:
        path = os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "data", "anim", name + ".json")
        try:
            with open(path) as fh:
                _CACHE[name] = json.load(fh)
        except Exception:
            _CACHE[name] = None
    return _CACHE[name]


def clip_for(action):
    """The baked clip name for an action if a mocap clip exists, else None."""
    name = ACTION_CLIP.get(action)
    return name if (name and _load(name)) else None


def is_loop(name):
    c = _load(name)
    return bool(c and c.get("loop", True))


def sample_norm(name, phase):
    """Interpolate a clip at `phase` and return the raw normalized side-view
    {joint: (nx, ny)} (fore-aft, height) — the input to the P34.15 DEPTH model
    (nx becomes the fore-aft depth `w`, ny the height). None if the clip is absent."""
    clip = _load(name)
    if clip is None:
        return None
    keys, J = clip["keys"], clip["joints"]
    if clip.get("loop", True):
        fi = (phase % 1.0) * keys
        i0 = int(fi) % keys
        i1 = (i0 + 1) % keys
    else:
        fi = max(0.0, min(0.9999, phase)) * (keys - 1)
        i0 = int(fi)
        i1 = min(keys - 1, i0 + 1)
    f = fi - int(fi)
    out = {}
    for j in _JOINTS:
        a, b = J[j][i0], J[j][i1]
        out[j] = (a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f)
    return out


def pose_from_clip(name, phase, cx, foot_y, H, facing, build=None):
    """Interpolate the clip at `phase` and map to a screen pose dict. `phase`
    is 0..1 within the clip (loops wrap). Mirrors x by the facing sign."""
    clip = _load(name)
    if clip is None:
        return None
    keys = clip["keys"]
    J = clip["joints"]
    if clip.get("loop", True):
        fi = (phase % 1.0) * keys
        i0 = int(fi) % keys
        i1 = (i0 + 1) % keys
    else:
        fi = max(0.0, min(0.9999, phase)) * (keys - 1)
        i0 = int(fi)
        i1 = min(keys - 1, i0 + 1)
    f = fi - int(fi)
    fdir = facing[0] if facing[0] else 1
    pose = {}
    for j in _JOINTS:
        a, b = J[j][i0], J[j][i1]
        nx = a[0] + (b[0] - a[0]) * f
        ny = a[1] + (b[1] - a[1]) * f
        pose[j] = (cx + nx * H * fdir, foot_y - ny * H)
    from ui.char_pose import HEAD_R
    head_mult = (build or {}).get("head", 1.0)
    pose["head_r"] = max(2, int(H * HEAD_R * head_mult))
    pose["facing"] = facing
    pose["fdir"] = fdir
    pose["profile"] = fdir              # side view → a profile face
    pose["girth"] = (build or {}).get("girth", 1.0)
    pose["H"] = H
    return pose
