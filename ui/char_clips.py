"""P33.6b animation CLIPS — a library of procedural pose transforms.

The rest / walk / attack skeleton comes from `char_pose`; this module adds a
growing library of ACTION clips (jump, sit, bow, wave, guard, hurt, cast, stoop,
dance, cheer, leap, run) that TRANSFORM that skeleton for a phase. `apply(action,
pose, phase, H, facing)` dispatches; one-shot clips run over a `duration`, loops
read a continuous phase. Pure joint math — headless-testable; `body_renderer`
picks the action in `update_anim` and blits the result.
"""

import math

# action -> (one_shot?, duration_seconds | None for a held loop)
ACTIONS = {
    "idle": (False, None), "walk": (False, None), "run": (False, None),
    "attack": (False, None), "guard": (False, None), "sit": (False, None),
    "sleep": (False, None), "dance": (False, None),
    "jump": (True, 0.7), "leap": (True, 0.7), "bow": (True, 1.1),
    "wave": (True, 1.0), "hurt": (True, 0.45), "cast": (True, 0.9),
    "stoop": (True, 1.0), "cheer": (True, 1.0),
}

_JOINTS = ["l_hip", "r_hip", "chest", "l_knee", "r_knee", "l_foot", "r_foot",
           "l_sh", "r_sh", "neck", "head", "l_elbow", "l_hand",
           "r_elbow", "r_hand"]
_UPPER = ["chest", "l_sh", "r_sh", "neck", "head",
          "l_elbow", "l_hand", "r_elbow", "r_hand"]


def is_one_shot(action):
    return ACTIONS.get(action, (False, None))[0]


def duration(action):
    return ACTIONS.get(action, (False, None))[1]


def _arc(t):                      # 0 → 1 → 0 over t in [0, 1]
    return math.sin(max(0.0, min(1.0, t)) * math.pi)


def _fdir(facing):
    return facing[0] if facing[0] else 0


def _move(pose, keys, dx, dy):
    for k in keys:
        if k in pose:
            pose[k] = (pose[k][0] + dx, pose[k][1] + dy)


def apply(action, pose, phase, H, facing):
    fn = _CLIPS.get(action)
    return fn(dict(pose), phase, H, facing) if fn else pose


# ---- the clips ----------------------------------------------------------

def _jump(pose, t, H, facing):
    up = _arc((t - 0.12) / 0.88) * H * 0.30
    _move(pose, _JOINTS, 0, -up)
    _move(pose, ("l_foot", "r_foot", "l_knee", "r_knee"), 0, -up * 0.4)
    return pose


def _leap(pose, t, H, facing):
    pose = _jump(pose, t, H, facing)
    _move(pose, _JOINTS, _fdir(facing) * _arc(t) * H * 0.10, 0)
    return pose


def _sit(pose, t, H, facing):
    drop = H * 0.22
    _move(pose, ("l_hip", "r_hip", "chest") + tuple(_UPPER), 0, drop)
    hipy = pose["l_hip"][1]
    for hipk, kneek, footk in (("l_hip", "l_knee", "l_foot"),
                               ("r_hip", "r_knee", "r_foot")):
        hx = pose[hipk][0]
        pose[kneek] = (hx + H * 0.12, hipy + H * 0.02)
        pose[footk] = (hx + H * 0.22, hipy + H * 0.14)
    return pose


def _sleep(pose, t, H, facing):
    pose = _sit(pose, t, H, facing)
    _move(pose, _UPPER, 0, H * 0.05)          # slumped
    return pose


def _bow(pose, t, H, facing):
    d = _arc(t)
    _move(pose, _UPPER, _fdir(facing) * H * 0.22 * d, H * 0.14 * d)
    return pose


def _stoop(pose, t, H, facing):
    d = _arc(t)
    f = _fdir(facing) or 1
    _move(pose, _UPPER, f * H * 0.10 * d, H * 0.20 * d)
    pose["r_hand"] = (pose["r_hand"][0] + f * H * 0.10 * d,
                      pose["l_foot"][1] - H * 0.02)
    return pose


def _wave(pose, t, H, facing):
    s = pose["r_sh"]
    wig = math.sin(t * math.pi * 6) * H * 0.05
    pose["r_hand"] = (s[0] + H * 0.10 + wig, s[1] - H * 0.30)
    pose["r_elbow"] = (s[0] + H * 0.08, s[1] - H * 0.10)
    return pose


def _guard(pose, t, H, facing):
    _move(pose, _JOINTS, 0, H * 0.03)          # crouch
    s, f = pose["l_sh"], (_fdir(facing) or 1)
    pose["l_hand"] = (s[0] + f * H * 0.14, s[1] + H * 0.05)
    pose["l_elbow"] = (s[0] + f * H * 0.08, s[1] + H * 0.10)
    return pose


def _hurt(pose, t, H, facing):
    j = _arc(t)
    f = _fdir(facing)
    _move(pose, _UPPER, -f * H * 0.10 * j, -H * 0.02 * j)
    pose["l_hand"] = (pose["l_hand"][0] - H * 0.06 * j,
                      pose["l_hand"][1] - H * 0.05 * j)
    return pose


def _cast(pose, t, H, facing):
    r = _arc(t)
    for hand, sh, el in (("l_hand", "l_sh", "l_elbow"),
                         ("r_hand", "r_sh", "r_elbow")):
        s = pose[sh]
        pose[hand] = (s[0], s[1] - H * 0.22 * r)
        pose[el] = (s[0], s[1] - H * 0.09 * r)
    return pose


def _dance(pose, t, H, facing):
    sway = math.sin(t * math.pi * 4)
    hop = abs(math.sin(t * math.pi * 4)) * H * 0.04
    _move(pose, _JOINTS, sway * H * 0.03, -hop)
    pose["l_hand"] = (pose["l_sh"][0] - H * 0.05,
                      pose["l_sh"][1] - H * 0.15 * (0.5 + 0.5 * sway))
    pose["r_hand"] = (pose["r_sh"][0] + H * 0.05,
                      pose["r_sh"][1] - H * 0.15 * (0.5 - 0.5 * sway))
    return pose


def _cheer(pose, t, H, facing):
    u = _arc(t)
    _move(pose, _JOINTS, 0, -u * H * 0.06)
    pose["l_hand"] = (pose["l_sh"][0] - H * 0.04, pose["l_sh"][1] - H * 0.28 * u)
    pose["r_hand"] = (pose["r_sh"][0] + H * 0.04, pose["r_sh"][1] - H * 0.28 * u)
    return pose


def _run(pose, t, H, facing):
    _move(pose, _UPPER, _fdir(facing) * H * 0.06, 0)   # forward lean
    return pose


_CLIPS = {
    "jump": _jump, "leap": _leap, "sit": _sit, "sleep": _sleep, "bow": _bow,
    "stoop": _stoop, "wave": _wave, "guard": _guard, "hurt": _hurt,
    "cast": _cast, "dance": _dance, "cheer": _cheer, "run": _run,
}
