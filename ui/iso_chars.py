"""P41.5 — baked 3D character figures for the isometric world.

A character is a small stacked-box humanoid (legs / torso / head / hair + a
facing nub) rasterised ONCE via `raster3d.bake` into a cached iso sprite, tinted
by the character's armour/class so folk read apart, with a 4-direction FACING so
they turn. `iso_render` places them + a contact shadow, depth-sorted with the
world (a hero stands correctly in front of / behind a building or tree).
"""

import math

import numpy as np

from ui import raster3d as r3

_CACHE = {}
# a tighter camera than the default object cam so the ~1-unit figure fills the
# sprite (characters read bigger than a single tile)
_CHAR_CAM = dict(cam_pos=(2.1, 2.5, -2.5), look=(0.0, 0.55, 0.0),
                 vfov_deg=27.0)

_CLASS_COLOR = {
    "warrior": (150, 150, 165), "guard": (120, 130, 150),
    "paladin": (170, 165, 140), "wizard": (96, 70, 150),
    "sorcerer": (120, 60, 150), "warlock": (70, 60, 110),
    "cleric": (200, 195, 175), "druid": (90, 120, 70),
    "rogue": (80, 80, 92), "ranger": (80, 110, 70),
    "bard": (170, 110, 150), "merchant": (150, 120, 80),
    "villager": (150, 130, 100), "noble": (120, 90, 150),
    "monster": (90, 130, 80), "troll": (110, 130, 90),
    "brigand": (110, 80, 70), "animal": (140, 110, 80),
}
_SKIN = (232, 196, 160)
_LEG = (56, 52, 64)


def _tint(char):
    base = _CLASS_COLOR.get(getattr(getattr(char, "character_class", None),
                                    "value", ""), (120, 120, 140))
    try:
        from ui import char_motion
        return tuple(char_motion.armor_tint(char, base))
    except Exception:
        return base


def _hair(char):
    from ui.sprite_loader import PALETTE
    return PALETTE.get(getattr(char, "hair", "") or "hair_brown",
                       PALETTE["hair_brown"])


def _rot_y(verts, a):
    c, s = math.cos(a), math.sin(a)
    m = np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])
    return verts @ m.T


def _rot_z_about(verts, a, pivot):
    """Rotate `verts` by `a` about the z axis through `pivot` (a head tilt)."""
    c, s = math.cos(a), math.sin(a)
    p = np.array(pivot, float)
    m = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])
    return (verts - p) @ m.T + p


def _rot_x_about(verts, a, pivot):
    """Rotate about the x axis through `pivot` — a fore-aft LIMB SWING (legs +
    arms swing in the walk direction, before facing is applied)."""
    c, s = math.cos(a), math.sin(a)
    p = np.array(pivot, float)
    m = np.array([[1, 0, 0], [0, c, -s], [0, s, c]])
    return (verts - p) @ m.T + p


# rest-figure part indices: 0 L-leg 1 R-leg 2 waist 3 chest 4 L-arm 5 R-arm
# 6 head 7 hair 8 nose
def _rest_parts(tint, hair, stance):
    lean = (stance - 1) * 0.05                  # weight shift: -0.05 / 0 / +0.05
    tilt = (stance - 1) * 0.10                  # head tilt to match
    fwd = (stance - 1) * 0.05                   # a forward-carried arm
    dark = tuple(int(v * 0.82) for v in tint)   # shaded limbs read apart
    parts = [
        r3.box(-0.10, 0.0, 0, 0.16, 0.74, 0.22, _LEG),        # left leg
        r3.box(0.10, 0.0, 0, 0.16, 0.74, 0.22, _LEG),         # right leg
        r3.box(lean * 0.5, 0.70, 0, 0.34, 0.24, 0.24, tint),  # waist
        r3.box(lean, 0.92, 0, 0.46, 0.30, 0.26, tint),        # chest/shoulders
        r3.box(lean - 0.29, 0.62, -fwd, 0.12, 0.54, 0.14, dark),  # left arm
        r3.box(lean + 0.29, 0.62, fwd, 0.12, 0.54, 0.14, dark),   # right arm
        r3.box(lean, 1.18, 0, 0.24, 0.24, 0.24, _SKIN),       # head
        r3.box(lean, 1.36, 0, 0.27, 0.10, 0.27, hair),        # hair cap
        r3.box(lean, 1.22, 0.15, 0.09, 0.08, 0.08, _SKIN),    # nose (facing cue)
    ]
    if tilt:
        for i in (6, 7, 8):
            parts[i] = (_rot_z_about(parts[i][0], tilt, (lean, 1.2, 0)),
                        parts[i][1], parts[i][2])
    return parts


def _lift(part, dy):
    v, t, c = part
    return (v + np.array([0.0, dy, 0.0]), t, c)


def _pose(parts, action, phase):
    """ISO.4: animate the rest figure — a WALK stride, an ATTACK swing, or a
    breathing IDLE — at `phase` (0..1). Boxes swing about their hip/shoulder
    pivots; the upper body bobs."""
    two_pi = 2.0 * math.pi
    p = [pp for pp in parts]
    LH, RH = (-0.10, 0.74, 0.0), (0.10, 0.74, 0.0)   # hip pivots
    LS, RS = (-0.29, 1.16, 0.0), (0.29, 1.16, 0.0)   # shoulder pivots
    if action == "walk":
        sw = math.sin(phase * two_pi) * 0.55
        bob = abs(math.sin(phase * two_pi * 2)) * 0.04
        p[0] = (_rot_x_about(parts[0][0], sw, LH), parts[0][1], parts[0][2])
        p[1] = (_rot_x_about(parts[1][0], -sw, RH), parts[1][1], parts[1][2])
        p[4] = (_rot_x_about(parts[4][0], -sw * 0.8, LS), parts[4][1], parts[4][2])
        p[5] = (_rot_x_about(parts[5][0], sw * 0.8, RS), parts[5][1], parts[5][2])
        for i in (2, 3, 6, 7, 8):
            p[i] = _lift(parts[i], bob)
    elif action == "attack":
        a = math.sin(phase * math.pi)                # 0..1..0
        p[5] = (_rot_x_about(parts[5][0], -a * 1.5, RS),
                parts[5][1], parts[5][2])            # weapon arm arcs up/over
        p[3] = _lift(parts[3], a * 0.02)
    else:                                            # idle breathing / sway
        bob = math.sin(phase * two_pi) * 0.018
        sw = math.sin(phase * two_pi) * 0.06
        p[4] = (_rot_x_about(parts[4][0], sw, LS), parts[4][1], parts[4][2])
        p[5] = (_rot_x_about(parts[5][0], -sw, RS), parts[5][1], parts[5][2])
        for i in (2, 3, 6, 7, 8):
            p[i] = _lift(parts[i], bob)
    return p


def _figure(tint, hair, facing, stance=1, action="idle", phase=0.0):
    parts = _pose(_rest_parts(tint, hair, stance), action, phase)
    a = (facing % 4) * (math.pi / 2)
    return [(_rot_y(np.asarray(v), a), t, c) for v, t, c in parts]


def _stance_of(char) -> int:
    """A stable 0-2 stance (weight-left / neutral / weight-right) per person."""
    h = 0
    for ch in (getattr(char, "id", "") or getattr(char, "name", "") or "x"):
        h = (h * 131 + ord(ch)) & 0x7fffffff
    return h % 3


def facing_of(char) -> int:
    """A 0-3 facing from the character's anim state, else 2 (toward camera)."""
    try:
        from ui import char_motion
        anim = (getattr(char, "metadata", {}) or {}).get("_anim", {})
        f = char_motion.facing(anim)
        return {"south": 2, "north": 0, "east": 1, "west": 3}.get(f, 2)
    except Exception:
        return 2


_FRAMES = {"walk": 8, "attack": 6, "idle": 6}          # ISO.6 smoother mocap
_PERIOD = {"walk": 720, "attack": 460, "idle": 2600}   # ms per cycle
_WALK_HOLD, _ATTACK_HOLD = 480, 420


def _clock_ms() -> int:
    try:
        import pygame
        return pygame.time.get_ticks()
    except Exception:
        return 0


def _frame_state(char):
    """ISO.4: (action, frame) — WALK while the character moves tile-to-tile,
    ATTACK on a fresh strike (a bumped `_atk_seq`), else a breathing IDLE.
    Transient per-character render state on `metadata` (not saved)."""
    md = getattr(char, "metadata", None)
    if md is None:
        return "idle", 0
    now = _clock_ms()
    seq = md.get("_atk_seq", 0)                       # strike counter
    if seq != md.get("_iso_atk_seq", seq):
        md["_iso_atk_until"] = now + _ATTACK_HOLD
    md["_iso_atk_seq"] = seq
    pos = getattr(char, "position", None)
    if pos is not None and pos != md.get("_iso_pos", pos):
        md["_iso_walk_until"] = now + _WALK_HOLD
    md["_iso_pos"] = pos
    off = _stance_of(char) * 400                      # desync folk
    if now < md.get("_iso_atk_until", 0):
        act = "attack"
    elif now < md.get("_iso_walk_until", 0):
        act = "walk"
    else:
        act = "idle"
    n, per = _FRAMES[act], _PERIOD[act]
    return act, int(((now + off) / per) * n) % n


def char_sprite(char, size: int, facing=None):
    if facing is None:
        facing = facing_of(char)
    tint, hair = _tint(char), _hair(char)
    action, frame = _frame_state(char)
    key = (tint, hair, size, facing % 4, action, frame)
    if key not in _CACHE:
        phase = frame / _FRAMES[action]
        from ui import iso_skeleton
        # ISO.6: a real Mixamo-mocap-driven rigged skeleton; if the clip is
        # missing, fall back to the ISO.3/4 procedural box figure.
        mesh = iso_skeleton.sample_figure(action, phase, tint, hair, facing)
        cam = iso_skeleton.CAM
        if mesh is None:
            mesh = _figure(tint, hair, facing, _stance_of(char), action, phase)
            cam = _CHAR_CAM
        _CACHE[key] = r3.bake(mesh, size=size, **cam)
    return _CACHE[key]
