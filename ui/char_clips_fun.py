"""P34.13 — comedy & dance clips: jigs, taunts and silly moves.

Funny, characterful animations that make the cast entertaining to watch and give
the hero something to DO. Same transform contract as `char_clips`
(`fn(pose, phase, H, facing) -> pose`); merged into that registry at import. Pure
joint math; headless-testable. A separate file purely to hold under 500 lines.
"""

from ui.char_clips_util import (math, _JOINTS, _UPPER, _arc, _ease, _fdir, _move,
                                _centroid, _rotate)

# action -> (one_shot?, duration) — dances run a beat or two then settle
ACTIONS_FUN = {
    "jig": (True, 1.8), "kick": (True, 1.6), "moonwalk": (True, 1.8),
    "robot": (True, 1.8), "flex": (True, 1.3), "taunt": (True, 1.4),
    "wiggle": (True, 1.6), "disco": (True, 1.8), "airguitar": (True, 1.6),
    "facepalm2": (True, 1.2),
}


def _jig(pose, t, H, facing):
    """A lively Irish jig — fast little hops with alternating high knees."""
    beat = math.sin(t * math.pi * 8)
    _move(pose, _JOINTS, 0, -abs(beat) * H * 0.05)
    up = H * 0.14 * abs(beat)
    if beat > 0:
        pose["r_knee"] = (pose["r_knee"][0], pose["r_knee"][1] - up)
        pose["r_foot"] = (pose["r_foot"][0], pose["r_foot"][1] - up * 1.5)
    else:
        pose["l_knee"] = (pose["l_knee"][0], pose["l_knee"][1] - up)
        pose["l_foot"] = (pose["l_foot"][0], pose["l_foot"][1] - up * 1.5)
    for hand, sh in (("l_hand", "l_sh"), ("r_hand", "r_sh")):   # arms stiff at sides
        s = pose[sh]
        pose[hand] = (s[0], s[1] + H * 0.24)
    return pose


def _kick(pose, t, H, facing):
    """A can-can high kick — legs fling up forward in turn, arms out for balance."""
    f, beat = (_fdir(facing) or 1), math.sin(t * math.pi * 4)
    _move(pose, _JOINTS, 0, -abs(beat) * H * 0.04)
    if beat > 0:
        pose["r_foot"] = (pose["r_hip"][0] + f * H * 0.32 * beat,
                          pose["r_hip"][1] - H * 0.12 * beat)
        pose["r_knee"] = (pose["r_hip"][0] + f * H * 0.16 * beat, pose["r_hip"][1])
    else:
        pose["l_foot"] = (pose["l_hip"][0] - f * H * 0.32 * beat,
                          pose["l_hip"][1] + H * 0.12 * beat)
        pose["l_knee"] = (pose["l_hip"][0] - f * H * 0.16 * beat, pose["l_hip"][1])
    for hand, sh, s in (("l_hand", "l_sh", -1), ("r_hand", "r_sh", 1)):
        p = pose[sh]
        pose[hand] = (p[0] + s * H * 0.16, p[1] - H * 0.02)
    return pose


def _moonwalk(pose, t, H, facing):
    """A smooth backslide — feet shuffle, the body glides the 'wrong' way."""
    f, s = (_fdir(facing) or 1), math.sin(t * math.pi * 2)
    pose["l_foot"] = (pose["l_foot"][0] - f * H * 0.10 * (0.5 + 0.5 * s),
                      pose["l_foot"][1])
    pose["r_foot"] = (pose["r_foot"][0] - f * H * 0.10 * (0.5 - 0.5 * s),
                      pose["r_foot"][1] - H * 0.03 * max(0.0, s))
    _move(pose, ("chest", "neck", "head", "l_sh", "r_sh"), -f * H * 0.03, 0)
    pose["r_hand"] = (pose["r_sh"][0] + f * H * 0.06, pose["r_sh"][1] - H * 0.10)
    return pose


def _robot(pose, t, H, facing):
    """The robot — quantized, jerky arm angles."""
    step = math.floor(t * 8) / 8.0
    a = step * math.pi * 2
    for hand, el, sh, ph in (("l_hand", "l_elbow", "l_sh", 0.0),
                             ("r_hand", "r_elbow", "r_sh", math.pi)):
        p = pose[sh]
        up = 0.5 + 0.5 * math.sin(a + ph)
        pose[el] = (p[0] + (H * 0.12 if sh == "r_sh" else -H * 0.12), p[1] + H * 0.06)
        pose[hand] = (pose[el][0], p[1] + H * 0.22 - up * H * 0.30)
    return pose


def _flex(pose, t, H, facing):
    """A muscle flex — both arms curl up, fists by the head, chest puffed."""
    d = _arc(t)
    for hand, el, sh, s in (("l_hand", "l_elbow", "l_sh", -1),
                            ("r_hand", "r_elbow", "r_sh", 1)):
        p = pose[sh]
        pose[el] = (p[0] + s * H * 0.16 * d, p[1] + H * 0.04)
        pose[hand] = (p[0] + s * H * 0.04, p[1] - H * 0.10 * d)
    _move(pose, ("chest",), 0, -H * 0.02 * d)
    return pose


def _taunt(pose, t, H, facing):
    """Come-at-me — both hands beckon while the chest juts forward, cocky."""
    f, beck = (_fdir(facing) or 1), math.sin(t * math.pi * 4)
    for hand, sh in (("l_hand", "l_sh"), ("r_hand", "r_sh")):
        p = pose[sh]
        pose[hand] = (p[0] + f * H * (0.12 + 0.05 * beck), p[1] + H * 0.06)
    _move(pose, ("chest", "neck", "head"), f * H * 0.03, 0)
    return pose


def _wiggle(pose, t, H, facing):
    """A silly shimmy — hips and shoulders sway opposite ways."""
    w = math.sin(t * math.pi * 6)
    _move(pose, ("l_hip", "r_hip", "chest"), w * H * 0.04, 0)
    _move(pose, ("l_sh", "r_sh", "neck", "head"), -w * H * 0.03, 0)
    for hand, sh, s in (("l_hand", "l_sh", -1), ("r_hand", "r_sh", 1)):
        p = pose[sh]
        pose[hand] = (p[0] + s * H * 0.10, p[1] - H * 0.08 * (0.5 + 0.5 * w * s))
    return pose


def _disco(pose, t, H, facing):
    """Saturday-night point — one arm stabs up-diagonal, alternating on the beat."""
    f, beat = (_fdir(facing) or 1), math.sin(t * math.pi * 4)
    _move(pose, _JOINTS, 0, -abs(beat) * H * 0.03)
    if beat > 0:
        pose["r_hand"] = (pose["r_sh"][0] + f * H * 0.20, pose["r_sh"][1] - H * 0.28)
        pose["l_hand"] = (pose["l_sh"][0] - f * H * 0.10, pose["l_sh"][1] + H * 0.14)
    else:
        pose["r_hand"] = (pose["r_sh"][0] - f * H * 0.10, pose["r_sh"][1] + H * 0.14)
        pose["l_hand"] = (pose["l_sh"][0] + f * H * 0.20, pose["l_sh"][1] - H * 0.28)
    return pose


def _airguitar(pose, t, H, facing):
    """Air guitar — one hand strums low, the other frets high, head banging."""
    f, strum = (_fdir(facing) or 1), math.sin(t * math.pi * 6)
    _move(pose, ("head", "neck"), 0, abs(strum) * H * 0.03)          # head-bang
    pose["r_hand"] = (pose["r_sh"][0] + f * H * (0.10 + 0.06 * strum),
                      pose["r_sh"][1] + H * 0.16)                    # strum low
    pose["l_hand"] = (pose["l_sh"][0] + f * H * 0.14,
                      pose["l_sh"][1] - H * 0.02)                    # fret high
    pose["l_elbow"] = (pose["l_sh"][0] + f * H * 0.08, pose["l_sh"][1] + H * 0.06)
    return pose


def _facepalm2(pose, t, H, facing):
    """A big two-hand facepalm of despair, head sinking."""
    d = _arc(t)
    head = pose["head"]
    for hand, sh in (("l_hand", "l_sh"), ("r_hand", "r_sh")):
        s = pose[sh]
        pose[hand] = (s[0] + (head[0] - s[0]) * d,
                      s[1] + (head[1] - s[1]) * d + H * 0.02)
    _move(pose, ("head", "neck"), 0, H * 0.04 * d)
    return pose


CLIPS_FUN = {
    "jig": _jig, "kick": _kick, "moonwalk": _moonwalk, "robot": _robot,
    "flex": _flex, "taunt": _taunt, "wiggle": _wiggle, "disco": _disco,
    "airguitar": _airguitar, "facepalm2": _facepalm2,
}
