"""P34.10 — the expanded procedural clip library: acrobatics & daily life.

A big second batch of ACTION clips (flips, rolls, cartwheels, a lunge, crawling,
crouching, eating, drinking, resting, stretching, yawning, clapping, laughing…) so
the cast has real behavioural variety and reads as ALIVE. Same transform contract
as `char_clips` — `fn(pose, phase, H, facing) -> pose` — merged into that module's
registry at import time. Pure joint math; headless-testable. Kept separate purely
to hold every file under 500 lines.
"""

from ui.char_clips_util import (math, _JOINTS, _UPPER, _arc, _ease, _fdir, _move,
                                _feet_pivot, _centroid, _rotate)

# action -> (one_shot?, duration | None for a held loop)
ACTIONS_MORE = {
    # acrobatics
    "flip": (True, 0.8), "somersault": (True, 0.8), "cartwheel": (True, 0.9),
    "roll": (True, 0.6), "twirl": (True, 0.9),
    # combat / movement
    "lunge": (True, 0.5), "crawl": (False, None), "crouch": (False, None),
    # daily life
    "eat": (True, 1.6), "drink": (True, 1.0), "rest": (False, None),
    "lie": (False, None), "stretch": (True, 1.2), "yawn": (True, 1.4),
    "clap": (True, 1.2), "laugh": (True, 1.4), "shrug": (True, 0.8),
    "ponder": (True, 1.6), "salute": (True, 1.2), "beckon": (True, 1.0),
    "facepalm": (True, 1.4), "winded": (True, 1.8),
    # P34.11 cast-gesture variants (chosen per caster by char_style)
    "cast_point": (True, 0.9), "cast_staff": (True, 0.9),
}


def _winded(pose, t, H, facing):
    """Out of breath — hunch forward, hands to the knees, chest heaving."""
    d, f = _arc(t), (_fdir(facing) or 1)
    _move(pose, _UPPER, f * H * 0.10 * d, H * 0.11 * d)     # lean forward + down
    for hand, hip in (("l_hand", "l_hip"), ("r_hand", "r_hip")):
        pose[hand] = (pose[hip][0] + f * H * 0.02, pose[hip][1] - H * 0.02)
    _move(pose, ("chest", "neck", "head"), 0,
          math.sin(t * math.pi * 7) * H * 0.012 * d)        # heavy breathing
    return pose


# ---- spell-cast variants (P34.11) --------------------------------------

def _cast_point(pose, t, H, facing):
    """A directed cast — the near hand thrusts a bolt forward, the other drawn
    back to gather power."""
    d, f = _arc(t), (_fdir(facing) or 1)
    s = pose["r_sh"]
    pose["r_hand"] = (s[0] + f * H * 0.28 * d, s[1] - H * 0.04 * d)
    pose["r_elbow"] = (s[0] + f * H * 0.14 * d, s[1] - H * 0.02 * d)
    ls = pose["l_sh"]
    pose["l_hand"] = (ls[0] - f * H * 0.10 * d, ls[1] + H * 0.06)
    return pose


def _cast_staff(pose, t, H, facing):
    """A staff cast — raise the staff high, then sweep it down and forward."""
    f, s = (_fdir(facing) or 1), pose["r_sh"]
    if t < 0.5:
        u = _ease(t / 0.5)
        pose["r_hand"] = (s[0] + f * H * 0.04, s[1] - H * 0.30 * u)
        pose["r_elbow"] = (s[0] + f * H * 0.02, s[1] - H * 0.12 * u)
    else:
        u = _ease((t - 0.5) / 0.5)
        pose["r_hand"] = (s[0] + f * H * (0.04 + 0.24 * u),
                          s[1] - H * 0.30 + H * 0.30 * u)
        pose["r_elbow"] = (s[0] + f * H * (0.02 + 0.12 * u),
                           s[1] - H * 0.12 + H * 0.14 * u)
    return pose


# ---- acrobatics --------------------------------------------------------

def _flip(pose, t, H, facing):
    """A backflip: rise in an arc while the whole body rotates a full turn, knees
    tucked at the apex, landing upright."""
    _move(pose, _JOINTS, 0, -_arc(t) * H * 0.50)
    f = _fdir(facing) or 1
    cx, cy = _centroid(pose)
    _rotate(pose, _JOINTS, cx, cy, -f * 2 * math.pi * _ease(t))
    tuck = _arc(t)
    for k in ("l_knee", "r_knee", "l_foot", "r_foot"):
        x, y = pose[k]
        pose[k] = (x + (cx - x) * 0.35 * tuck, y + (cy - y) * 0.35 * tuck)
    return pose


def _somersault(pose, t, H, facing):
    """A forward air-roll: travels forward, rotates forward, tightly tucked."""
    f = _fdir(facing) or 1
    _move(pose, _JOINTS, f * _ease(t) * H * 0.35, -_arc(t) * H * 0.35)
    cx, cy = _centroid(pose)
    _rotate(pose, _JOINTS, cx, cy, f * 2 * math.pi * _ease(t))
    tuck = _arc(t)
    for k in ("l_knee", "r_knee", "l_foot", "r_foot", "head", "neck"):
        x, y = pose[k]
        pose[k] = (x + (cx - x) * 0.4 * tuck, y + (cy - y) * 0.4 * tuck)
    return pose


def _cartwheel(pose, t, H, facing):
    """Sideways full-turn on splayed limbs — a spinning star that travels."""
    f = _fdir(facing) or 1
    _move(pose, _JOINTS, f * _ease(t) * H * 0.45, 0)
    cx, cy = _centroid(pose)
    _rotate(pose, _JOINTS, cx, cy, f * 2 * math.pi * _ease(t))
    star = _arc(t)
    for k, (sx, sy) in (("l_hand", (-1, -1)), ("r_hand", (1, -1)),
                        ("l_foot", (-1, 1)), ("r_foot", (1, 1))):
        x, y = pose[k]
        pose[k] = (x + sx * H * 0.05 * star, y + sy * H * 0.05 * star)
    return pose


def _roll(pose, t, H, facing):
    """A dodge roll: tuck into a low ball, roll a full turn forward, come up."""
    f = _fdir(facing) or 1
    ball, lowy = _arc(t), _feet_pivot(pose)[1] - H * 0.12
    for k in _JOINTS:
        x, y = pose[k]
        pose[k] = (x + f * _ease(t) * H * 0.5, y + (lowy - y) * 0.55 * ball)
    cx, cy = _centroid(pose)
    _rotate(pose, _JOINTS, cx, cy, f * 2 * math.pi * _ease(t))
    return pose


def _twirl(pose, t, H, facing):
    """A pirouette: arms out, the body narrows then widens as it spins about its
    vertical axis (the 2D spin illusion), with a light lift."""
    for hand, sh, el, s in (("l_hand", "l_sh", "l_elbow", -1),
                            ("r_hand", "r_sh", "r_elbow", 1)):
        p = pose[sh]
        pose[hand] = (p[0] + s * H * 0.22, p[1] - H * 0.02)
        pose[el] = (p[0] + s * H * 0.12, p[1])
    cx, _cy = _centroid(pose)
    sx = math.cos(2 * math.pi * t)
    for k in _JOINTS:
        x, y = pose[k]
        pose[k] = (cx + (x - cx) * sx, y - _arc(t) * H * 0.03)
    return pose


# ---- combat / movement -------------------------------------------------

def _lunge(pose, t, H, facing):
    """A deep fencing lunge: front leg drives far forward and bends, back leg
    straightens, the weapon arm thrusts."""
    d, f = _arc(t), (_fdir(facing) or 1)
    _move(pose, ("l_hip", "r_hip", "chest") + tuple(_UPPER),
          f * H * 0.14 * d, H * 0.10 * d)
    pose["r_foot"] = (pose["r_hip"][0] + f * H * 0.34 * d, pose["r_foot"][1])
    pose["r_knee"] = (pose["r_hip"][0] + f * H * 0.20 * d,
                      pose["r_hip"][1] + H * 0.14)
    pose["l_foot"] = (pose["l_hip"][0] - f * H * 0.20 * d, pose["l_foot"][1])
    s = pose["r_sh"]
    pose["r_hand"] = (s[0] + f * H * 0.30 * d, s[1] + H * 0.02)
    pose["r_elbow"] = (s[0] + f * H * 0.16 * d, s[1] + H * 0.02)
    return pose


def _crawl(pose, t, H, facing):
    """On hands and knees, low to the ground, limbs reaching in alternation."""
    f, lowy = (_fdir(facing) or 1), _feet_pivot(pose)[1]
    _move(pose, _JOINTS, 0, H * 0.22)
    for hand, sh, ph in (("l_hand", "l_sh", 0.0), ("r_hand", "r_sh", math.pi)):
        s = pose[sh]
        reach = 0.5 + 0.5 * math.sin(t * math.pi * 2 + ph)
        pose[hand] = (s[0] + f * H * (0.10 + 0.06 * reach), lowy - H * 0.02)
    for knee, hip, foot in (("l_knee", "l_hip", "l_foot"),
                            ("r_knee", "r_hip", "r_foot")):
        pose[knee] = (pose[hip][0], lowy - H * 0.02)
        pose[foot] = (pose[hip][0] - f * H * 0.10, lowy)
    _move(pose, ("chest", "neck", "head", "l_sh", "r_sh"), f * H * 0.05, 0)
    return pose


def _crouch(pose, t, H, facing):
    """A held low, ready stance — knees bent, hands up and out."""
    _move(pose, _JOINTS, 0, H * 0.14)
    for knee, hip in (("l_knee", "l_hip"), ("r_knee", "r_hip")):
        pose[knee] = (pose[hip][0], pose[hip][1] + H * 0.10)
    for hand, sh, s in (("l_hand", "l_sh", -1), ("r_hand", "r_sh", 1)):
        p = pose[sh]
        pose[hand] = (p[0] + s * H * 0.10, p[1] + H * 0.04)
    return pose


# ---- daily life --------------------------------------------------------

def _eat(pose, t, H, facing):
    """Bringing food to the mouth in bites, with a small chewing bob."""
    bite = 0.5 + 0.5 * math.sin(t * math.pi * 3)
    head, s = pose["head"], pose["r_sh"]
    pose["r_hand"] = (head[0] - H * 0.04,
                      head[1] + H * 0.02 + (1 - bite) * H * 0.18)
    pose["r_elbow"] = ((s[0] + pose["r_hand"][0]) / 2, s[1] + H * 0.10)
    _move(pose, ("head",), 0, bite * H * 0.01)
    return pose


def _drink(pose, t, H, facing):
    """Tilt the head back, cup to the lips."""
    d, f = _arc(t), (_fdir(facing) or 1)
    head, s = pose["head"], pose["r_sh"]
    _move(pose, ("head",), -f * H * 0.03 * d, -H * 0.02 * d)
    pose["r_hand"] = (head[0], head[1] + H * 0.01 - H * 0.02 * d)
    pose["r_elbow"] = (s[0] + f * H * 0.02, s[1] + H * 0.06)
    return pose


def _rest(pose, t, H, facing):
    """Sit and lean back, legs out, hands planted behind for support."""
    f, drop = (_fdir(facing) or 1), H * 0.20
    _move(pose, ("l_hip", "r_hip") + tuple(_UPPER), -f * H * 0.04, drop)
    hipy = pose["l_hip"][1]
    for hip, knee, foot in (("l_hip", "l_knee", "l_foot"),
                            ("r_hip", "r_knee", "r_foot")):
        hx = pose[hip][0]
        pose[knee] = (hx + f * H * 0.16, hipy + H * 0.04)
        pose[foot] = (hx + f * H * 0.30, hipy + H * 0.10)
    _move(pose, ("chest", "neck", "head", "l_sh", "r_sh"), -f * H * 0.08, -H * 0.02)
    for hand, sh in (("l_hand", "l_sh"), ("r_hand", "r_sh")):
        pose[hand] = (pose[sh][0] - f * H * 0.10, hipy + H * 0.06)
    return pose


def _lie(pose, t, H, facing):
    """Lie flat on the ground (sleeping rough) — the standing body tipped over."""
    f, groundy = (_fdir(facing) or 1), _feet_pivot(pose)[1]
    cx, cy = _centroid(pose)
    _rotate(pose, _JOINTS, cx, cy, -f * math.pi / 2)
    lowest = max(pose[k][1] for k in _JOINTS)
    _move(pose, _JOINTS, 0, groundy - lowest)
    return pose


def _stretch(pose, t, H, facing):
    """Reach both arms high and arch upward — a satisfying stretch."""
    d = _arc(t)
    for hand, sh, el, s in (("l_hand", "l_sh", "l_elbow", -1),
                            ("r_hand", "r_sh", "r_elbow", 1)):
        p = pose[sh]
        pose[hand] = (p[0] + s * H * 0.04, p[1] - H * 0.30 * d)
        pose[el] = (p[0] + s * H * 0.03, p[1] - H * 0.14 * d)
    _move(pose, ("head", "neck", "chest"), 0, -H * 0.03 * d)
    return pose


def _yawn(pose, t, H, facing):
    """A drowsy yawn: head back, hand drifting to the mouth."""
    d, head, s = _arc(t), pose["head"], pose["l_sh"]
    _move(pose, ("head", "neck"), 0, -H * 0.02 * d)
    pose["l_hand"] = (head[0] - H * 0.05, head[1] + H * 0.04 * (1 - d))
    pose["l_elbow"] = (s[0], s[1] - H * 0.02)
    return pose


def _clap(pose, t, H, facing):
    """Hands meet in front, again and again."""
    m = abs(math.sin(t * math.pi * 4))
    cx = (pose["l_sh"][0] + pose["r_sh"][0]) / 2
    y, gap = pose["l_sh"][1] + H * 0.14, H * 0.10 * (1 - m)
    pose["l_hand"], pose["r_hand"] = (cx - gap, y), (cx + gap, y)
    pose["l_elbow"] = ((pose["l_sh"][0] + cx) / 2, pose["l_sh"][1] + H * 0.10)
    pose["r_elbow"] = ((pose["r_sh"][0] + cx) / 2, pose["r_sh"][1] + H * 0.10)
    return pose


def _laugh(pose, t, H, facing):
    """Head back, belly-shaking laughter, hands to the sides."""
    shake = math.sin(t * math.pi * 8) * H * 0.015
    _move(pose, ("head", "neck"), 0, -H * 0.02 + shake)
    _move(pose, ("chest", "l_sh", "r_sh"), 0, shake)
    for hand, sh in (("l_hand", "l_sh"), ("r_hand", "r_sh")):
        s = pose[sh]
        pose[hand] = (s[0] + (1 if sh[0] == "r" else -1) * H * 0.06, s[1] + H * 0.16)
    return pose


def _shrug(pose, t, H, facing):
    """A palms-up shrug — shoulders and hands up and out."""
    d = _arc(t)
    _move(pose, ("l_sh", "r_sh", "neck", "head"), 0, -H * 0.04 * d)
    for hand, sh, s in (("l_hand", "l_sh", -1), ("r_hand", "r_sh", 1)):
        p = pose[sh]
        pose[hand] = (p[0] + s * H * 0.16 * d, p[1] + H * 0.10)
    return pose


def _ponder(pose, t, H, facing):
    """A thoughtful beat — hand to the chin, head tilted."""
    d, head = _arc(t), pose["head"]
    pose["r_hand"] = (head[0] + H * 0.03, head[1] + H * 0.12 - H * 0.06 * d)
    pose["r_elbow"] = (pose["r_sh"][0], pose["r_sh"][1] + H * 0.14)
    _move(pose, ("head",), H * 0.02 * d, 0)
    return pose


def _salute(pose, t, H, facing):
    """A crisp salute — the near hand snaps to the brow."""
    d, head, s = _ease(min(1.0, t * 1.4)), pose["head"], pose["r_sh"]
    bx, by = head[0] + H * 0.05, head[1] - H * 0.02
    pose["r_hand"] = (s[0] + (bx - s[0]) * d, s[1] + (by - s[1]) * d)
    pose["r_elbow"] = (s[0] + H * 0.10 * d, s[1] + H * 0.04)
    return pose


def _beckon(pose, t, H, facing):
    """Waving someone closer — the hand curls inward, again and again."""
    f, curl, s = (_fdir(facing) or 1), math.sin(t * math.pi * 4), pose["r_sh"]
    pose["r_hand"] = (s[0] + f * H * (0.14 + 0.05 * curl), s[1] - H * 0.06)
    pose["r_elbow"] = (s[0] + f * H * 0.09, s[1])
    return pose


def _facepalm(pose, t, H, facing):
    """Hand to face, head sinking — exasperation."""
    d, head, s = _arc(t), pose["head"], pose["r_sh"]
    rx, ry = s[0] + H * 0.02, s[1] + H * 0.16
    pose["r_hand"] = (rx + (head[0] - rx) * d, ry + (head[1] - ry) * d)
    pose["r_elbow"] = (s[0] + H * 0.06 * d, s[1] + H * 0.08)
    _move(pose, ("head", "neck"), 0, H * 0.03 * d)
    return pose


CLIPS_MORE = {
    "flip": _flip, "somersault": _somersault, "cartwheel": _cartwheel,
    "roll": _roll, "twirl": _twirl, "lunge": _lunge, "crawl": _crawl,
    "crouch": _crouch, "eat": _eat, "drink": _drink, "rest": _rest, "lie": _lie,
    "stretch": _stretch, "yawn": _yawn, "clap": _clap, "laugh": _laugh,
    "shrug": _shrug, "ponder": _ponder, "salute": _salute, "beckon": _beckon,
    "facepalm": _facepalm, "cast_point": _cast_point, "cast_staff": _cast_staff,
    "winded": _winded,
}
