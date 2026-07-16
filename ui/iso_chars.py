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


def _figure(tint, hair, facing, stance=1):
    """ISO.3: an anthropometric stacked-box humanoid — two legs, a tapered
    torso, hanging ARMS, a proper head — in a seeded CONTRAPPOSTO stance (a
    lateral weight-shift + a head tilt + one arm carried forward) so folk read
    as bodies with natural weight, not stiff symmetric mannequins. ~1.6 tall."""
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
    ]
    head = [
        r3.box(lean, 1.18, 0, 0.24, 0.24, 0.24, _SKIN),       # head
        r3.box(lean, 1.36, 0, 0.27, 0.10, 0.27, hair),        # hair cap
        r3.box(lean, 1.22, 0.15, 0.09, 0.08, 0.08, _SKIN),    # nose (facing cue)
    ]
    if tilt:
        head = [(_rot_z_about(v, tilt, (lean, 1.2, 0)), t, c)
                for v, t, c in head]
    parts += head
    a = (facing % 4) * (math.pi / 2)
    return [(_rot_y(v, a), t, c) for v, t, c in parts]


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


def char_sprite(char, size: int, facing=None):
    if facing is None:
        facing = facing_of(char)
    tint, hair = _tint(char), _hair(char)
    stance = _stance_of(char)
    key = (tint, hair, size, facing % 4, stance)
    if key not in _CACHE:
        _CACHE[key] = r3.bake(_figure(tint, hair, facing, stance), size=size,
                              **_CHAR_CAM)
    return _CACHE[key]
