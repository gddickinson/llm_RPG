"""P33.6b animation CLIPS — a library of procedural pose transforms.

The rest / walk / attack skeleton comes from `char_pose`; this module adds a
growing library of ACTION clips (jump, sit, bow, wave, guard, hurt, cast, stoop,
dance, cheer, leap, run) that TRANSFORM that skeleton for a phase. `apply(action,
pose, phase, H, facing)` dispatches; one-shot clips run over a `duration`, loops
read a continuous phase. Pure joint math — headless-testable; `body_renderer`
picks the action in `update_anim` and blits the result.
"""

from ui.char_clips_util import (math, scale_pose, _JOINTS, _UPPER, _arc, _ease,
                                _fdir, _move, _feet_pivot)

# action -> (one_shot?, duration_seconds | None for a held loop)
ACTIONS = {
    "idle": (False, None), "walk": (False, None), "run": (False, None),
    "attack": (False, None), "guard": (False, None), "sit": (False, None),
    "sleep": (False, None), "dance": (False, None),
    "swim": (False, None), "climb": (False, None), "sneak": (False, None),
    "jog": (False, None),
    "jump": (True, 0.7), "leap": (True, 0.7), "bow": (True, 1.1),
    "wave": (True, 1.0), "hurt": (True, 0.45), "cast": (True, 0.9),
    "stoop": (True, 1.0), "cheer": (True, 1.0), "dodge": (True, 0.4),
    "kneel": (True, 1.6), "reach": (True, 0.7), "point": (True, 1.0),
    # two-character interactions (P33.6d)
    "handshake": (True, 1.2), "hug": (True, 1.4), "kiss": (True, 1.3),
    "wrestle": (True, 1.6), "throw": (True, 0.7), "tumble": (True, 0.9),
    "knockdown": (True, 1.6),
}


def is_one_shot(action):
    return ACTIONS.get(action, (False, None))[0]


def duration(action):
    return ACTIONS.get(action, (False, None))[1]


def apply(action, pose, phase, H, facing):
    fn = _CLIPS.get(action)
    return fn(dict(pose), phase, H, facing) if fn else pose


# ---- the clips ----------------------------------------------------------

def _jump(pose, t, H, facing):
    up = _arc((t - 0.12) / 0.88) * H * 0.30
    _move(pose, _JOINTS, 0, -up)
    _move(pose, ("l_foot", "r_foot", "l_knee", "r_knee"), 0, -up * 0.4)
    # squash & stretch (P34.1): crouch, stretch airborne, squash on landing
    if t < 0.12:
        s = t / 0.12
        sx, sy = 1 + 0.14 * s, 1 - 0.14 * s
    elif t > 0.88:
        s = (t - 0.88) / 0.12
        sx, sy = 1 + 0.20 * s, 1 - 0.20 * s
    else:
        sx, sy = 0.92, 1.12
    scale_pose(pose, sx, sy, _feet_pivot(pose))
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
    scale_pose(pose, 1 + 0.10 * j, 1 - 0.10 * j, _feet_pivot(pose))  # flinch squash
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


def _jog(pose, t, H, facing):
    _move(pose, _UPPER, _fdir(facing) * H * 0.03, 0)   # a light lean — easy pace
    return pose


def _swim(pose, t, H, facing):
    _move(pose, _JOINTS, 0, H * 0.14)                  # submerge to the chest
    stroke = math.sin(t * math.pi * 3)
    pose["l_hand"] = (pose["l_sh"][0] - H * 0.10,
                      pose["l_sh"][1] + H * 0.04 - stroke * H * 0.06)
    pose["r_hand"] = (pose["r_sh"][0] + H * 0.10,
                      pose["r_sh"][1] + H * 0.04 + stroke * H * 0.06)
    return pose


def _climb(pose, t, H, facing):
    r = math.sin(t * math.pi * 2)
    pose["l_hand"] = (pose["l_sh"][0] - H * 0.03,
                      pose["l_sh"][1] - H * 0.22 * (0.5 + 0.5 * r))
    pose["r_hand"] = (pose["r_sh"][0] + H * 0.03,
                      pose["r_sh"][1] - H * 0.22 * (0.5 - 0.5 * r))
    pose["l_foot"] = (pose["l_hip"][0], pose["l_foot"][1] - H * 0.05 * (0.5 - 0.5 * r))
    pose["r_foot"] = (pose["r_hip"][0], pose["r_foot"][1] - H * 0.05 * (0.5 + 0.5 * r))
    return pose


def _sneak(pose, t, H, facing):
    _move(pose, _JOINTS, 0, H * 0.06)                  # crouch low
    return pose


def _dodge(pose, t, H, facing):
    d = _arc(t)
    _move(pose, _JOINTS, H * 0.12 * d, -H * 0.03 * d)  # hop aside
    return pose


def _kneel(pose, t, H, facing):
    drop = H * 0.16
    _move(pose, ("l_hip", "r_hip", "chest") + tuple(_UPPER), 0, drop)
    pose["l_knee"] = (pose["l_hip"][0] - H * 0.05, pose["l_foot"][1] - H * 0.02)
    pose["r_knee"] = (pose["r_hip"][0] + H * 0.06, pose["r_hip"][1] + H * 0.06)
    pose["r_foot"] = (pose["r_hip"][0] + H * 0.14, pose["r_hip"][1] + drop)
    _move(pose, ("head", "neck"), 0, H * 0.04)
    return pose


def _reach(pose, t, H, facing):
    d, f = _arc(t), (_fdir(facing) or 1)
    s = pose["r_sh"]
    pose["r_hand"] = (s[0] + f * H * 0.22 * d, s[1] + H * 0.02)
    pose["r_elbow"] = (s[0] + f * H * 0.12 * d, s[1] + H * 0.06)
    _move(pose, ("chest", "l_sh", "r_sh", "neck", "head"), f * H * 0.05 * d, 0)
    return pose


def _point(pose, t, H, facing):
    d, f = _arc(t), (_fdir(facing) or 1)
    s = pose["r_sh"]
    pose["r_hand"] = (s[0] + f * H * 0.26 * d, s[1] - H * 0.08 * d)
    pose["r_elbow"] = (s[0] + f * H * 0.14 * d, s[1] - H * 0.04 * d)
    _move(pose, ("head", "neck"), f * H * 0.04 * d, 0)
    return pose


# ---- two-character interaction clips (P33.6d) --------------------------
# each poses ONE character; the pair reads as coordinated because both face each
# other and stand adjacent (see engine/anim.interact).

def _handshake(pose, t, H, facing):
    f = _fdir(facing) or 1
    shake = math.sin(t * math.pi * 5) * H * 0.02
    s = pose["r_sh"]
    pose["r_hand"] = (s[0] + f * H * 0.22, s[1] + H * 0.10 + shake)
    pose["r_elbow"] = (s[0] + f * H * 0.11, s[1] + H * 0.11)
    return pose


def _hug(pose, t, H, facing):
    d, f = _arc(t), (_fdir(facing) or 1)
    for hand, sh in (("l_hand", "l_sh"), ("r_hand", "r_sh")):
        s = pose[sh]
        pose[hand] = (s[0] + f * H * 0.17 * d, s[1] + H * 0.05)
    _move(pose, _UPPER, f * H * 0.05 * d, 0)
    return pose


def _kiss(pose, t, H, facing):
    d, f = _arc(t), (_fdir(facing) or 1)
    _move(pose, ("head", "neck", "chest", "l_sh", "r_sh"), f * H * 0.12 * d, 0)
    return pose


def _wrestle(pose, t, H, facing):
    f = _fdir(facing) or 1
    jostle = math.sin(t * math.pi * 4) * H * 0.03
    _move(pose, _JOINTS, f * H * 0.06 + jostle, H * 0.04)   # lean in, crouch
    for hand, sh in (("l_hand", "l_sh"), ("r_hand", "r_sh")):
        s = pose[sh]
        pose[hand] = (s[0] + f * H * 0.17, s[1])
    return pose


def _throw(pose, t, H, facing):
    f = _fdir(facing) or 1
    a = math.radians(-60 + 160 * _ease(t))
    s, arm = pose["r_sh"], H * 0.30
    pose["r_hand"] = (s[0] + f * arm * math.sin(a), s[1] - arm * math.cos(a))
    pose["r_elbow"] = ((s[0] + pose["r_hand"][0]) / 2,
                       (s[1] + pose["r_hand"][1]) / 2)
    return pose


def _tumble(pose, t, H, facing):
    d, f = _arc(t), _fdir(facing)
    _move(pose, _JOINTS, -f * H * 0.16 * d, -H * 0.05 * d)   # fly back + up
    pose["l_hand"] = (pose["l_hand"][0] - H * 0.08 * d, pose["l_hand"][1] - H * 0.06 * d)
    pose["r_hand"] = (pose["r_hand"][0] + H * 0.08 * d, pose["r_hand"][1] - H * 0.06 * d)
    return pose


def _knockdown(pose, t, H, facing):
    groundy, f = pose["l_foot"][1], _fdir(facing)
    if t < 0.3:
        d = _ease(t / 0.3)                     # fall
    elif t < 0.7:
        d = 1.0                                # lie there
    else:
        d = 1.0 - _ease((t - 0.7) / 0.3)       # get back up
    for k in _JOINTS:
        x, y = pose[k]
        pose[k] = (x - f * H * 0.12 * d, y + (groundy - y) * 0.7 * d)
    return pose


_CLIPS = {
    "jump": _jump, "leap": _leap, "sit": _sit, "sleep": _sleep, "bow": _bow,
    "stoop": _stoop, "wave": _wave, "guard": _guard, "hurt": _hurt,
    "cast": _cast, "dance": _dance, "cheer": _cheer, "run": _run, "jog": _jog,
    "swim": _swim, "climb": _climb, "sneak": _sneak, "dodge": _dodge,
    "kneel": _kneel, "reach": _reach, "point": _point,
    "handshake": _handshake, "hug": _hug, "kiss": _kiss, "wrestle": _wrestle,
    "throw": _throw, "tumble": _tumble, "knockdown": _knockdown,
}

# P34.10 — fold in the expanded acrobatics / daily-life library (kept in its own
# module so no file crosses 500 lines). Merged after the core so both dispatch
# through the same apply()/ACTIONS/duration.
from ui.char_clips_more import ACTIONS_MORE, CLIPS_MORE   # noqa: E402
ACTIONS.update(ACTIONS_MORE)
_CLIPS.update(CLIPS_MORE)

# P34.13 comedy & dance clips
from ui.char_clips_fun import ACTIONS_FUN, CLIPS_FUN       # noqa: E402
ACTIONS.update(ACTIONS_FUN)
_CLIPS.update(CLIPS_FUN)
