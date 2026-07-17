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


def _figure(tint, hair, angle, stance=1, action="idle", phase=0.0):
    parts = _pose(_rest_parts(tint, hair, stance), action, phase)
    return [(_rot_y(np.asarray(v), angle), t, c) for v, t, c in parts]


def _stance_of(char) -> int:
    """A stable 0-2 stance (weight-left / neutral / weight-right) per person."""
    h = 0
    for ch in (getattr(char, "id", "") or getattr(char, "name", "") or "x"):
        h = (h * 131 + ord(ch)) & 0x7fffffff
    return h % 3


# N, NE, E, SE, S, SW, W, NW — the 8 grid movement directions (world dx,dy)
_DELTAS = [(0, -1), (1, -1), (1, 0), (1, 1),
           (0, 1), (-1, 1), (-1, 0), (-1, -1)]


def move_delta(char):
    """The character's LAST MOVEMENT direction as a sign tuple (dx,dy) from
    `_anim['facing']` — one of the 8 grid directions, default south (0,1) when
    still. ISO.9 feeds this to `iso_skeleton.angle_for_delta` so the figure
    faces WHERE IT MOVES (was a broken world-azimuth quantisation)."""
    anim = (getattr(char, "metadata", {}) or {}).get("_anim", {})
    f = anim.get("facing", (0, 1))
    if isinstance(f, (tuple, list)) and len(f) == 2 and (f[0] or f[1]):
        sx = (f[0] > 0) - (f[0] < 0)
        sy = (f[1] > 0) - (f[1] < 0)
        return (sx, sy)
    return (0, 1)


# ISO.13 frames baked per action (a full loop, or the arc of a one-shot) + the
# ms period of a looping cycle. Higher frame counts on the common actions =
# SMOOTHER motion (baked once, cached). Any action not here reads as idle.
_ACT_FRAMES = {"walk": 12, "run": 12, "jog": 12, "idle": 8, "dance": 10,
               "sit": 4, "sleep": 4, "climb": 10, "talk": 8, "swim": 8,
               "attack": 8, "jump": 8, "leap": 8, "cheer": 8, "wave": 7,
               "cast": 7, "hurt": 5, "stagger": 6, "guard": 10, "crawl": 4,
               "kick": 8, "argue": 8, "sneak": 12, "stoop": 6, "dodge": 5,
               "shrug": 7, "ponder": 7, "yawn": 6, "stretch": 8, "reach": 7,
               "salute": 7, "beckon": 7, "facepalm": 7, "clap": 7, "laugh": 8,
               "point": 7, "nod": 6, "kneel": 5, "winded": 6,
               "cast_point": 7, "cast_staff": 7,
               # ISO.14 the new combat + gesture captures
               "fight_idle": 10, "jab": 8, "block": 7, "charge": 8, "stab": 8,
               "acknowledge": 8, "ask": 8, "bored": 10, "look": 10, "pray": 10,
               "no": 7, "silly": 12,
               # ISO.16 real sword combat / hit / cast / death
               "hit": 6, "spellcast": 9, "die": 9,
               # COMBAT.1 the attack + DEFENCE repertoire
               "block": 7, "shield_block": 7, "crouch_block": 7, "dodge": 8,
               "roll": 8, "hook": 8, "lead_jab": 7, "elbow": 8,
               "hit_head": 6, "hit_back": 7, "hit_legs": 6}
_LOOP_PERIOD = {"walk": 720, "run": 620, "jog": 760, "idle": 2600,
                "dance": 1100, "sit": 3000, "sleep": 3000, "climb": 1000,
                "talk": 1400, "swim": 900, "guard": 900, "crawl": 1400,
                "argue": 1400, "sneak": 1000, "stagger": 900,
                "fight_idle": 700, "bored": 2400, "look": 2200, "pray": 2600,
                "silly": 1100}
_ONESHOT = {"attack", "jump", "leap", "bow", "wave", "cast", "cheer",
            "stoop", "dodge", "hurt", "kick", "shrug", "ponder", "yawn",
            "stretch", "reach", "salute", "beckon", "facepalm", "clap",
            "laugh", "point", "nod", "kneel", "winded", "cast_point",
            "cast_staff", "jab", "block", "charge", "stab", "acknowledge",
            "ask", "no", "die", "shield_block", "crouch_block", "dodge", "roll",
            "hook", "lead_jab", "elbow", "hit_head", "hit_back", "hit_legs"}
# ISO.14 calm ambient GESTURES an idle character drifts into now and then (a
# glance around, a bored shift) so a standing crowd looks ALIVE — cosmetic,
# render-only, both LOOPS.
_AMBIENT_IDLE = ("idle", "idle", "idle", "idle", "look", "bored")


def _frames_of(action) -> int:
    return _ACT_FRAMES.get(action, 6)


def _clock_ms() -> int:
    try:
        import pygame
        return pygame.time.get_ticks()
    except Exception:
        return 0


def _ambient_idle(char):
    """ISO.14: a calm standing character drifts through idle → a glance → a
    bored shift → idle over a slow, per-person-desynced cycle (cosmetic), so a
    crowd never stands frozen."""
    slot_ms = 3700
    off = _stance_of(char) * slot_ms + (len(getattr(char, "id", "") or "") * 811)
    slot = ((_clock_ms() + off) // slot_ms) % len(_AMBIENT_IDLE)
    return _AMBIENT_IDLE[slot]


def _frame_state(char):
    """ISO.11 (action, frame): read the SAME `cur_action` the top-down renderer
    computes (`body_renderer.update_anim` — called for iso chars in ISO.8), so
    iso plays every animation — walk/run, jump, dance, sit, climb, talk, swim,
    an attack swing — not just walk/idle. A one-shot arcs through its timer; a
    looping action cycles on the clock (desynced per person)."""
    md = getattr(char, "metadata", None)
    if md is None:
        return "idle", 0
    try:                                              # ISO.16 a downed body LIES
        from ui.char_injury import injury_state
        if injury_state(char).get("down"):
            return "die", _frames_of("die") - 1       # the last frame = prone
    except Exception:
        pass
    anim = md.get("_anim") or {}
    action = anim.get("cur_action", "idle")
    if action not in _ACT_FRAMES:
        action = "idle"                               # unmapped → a calm idle
    if action == "idle":                              # ISO.14 ambient life
        action = _ambient_idle(char)
    n = _frames_of(action)
    if action in _ONESHOT:                            # progress through the arc
        if action == "attack":
            from ui.char_motion import ATTACK_DUR
            prog = 1.0 - anim.get("atk_t", 0.0) / max(ATTACK_DUR, 1e-6)
        else:
            prog = 1.0 - anim.get("action_t", 0.0) / max(
                anim.get("action_dur", 0.6), 1e-6)
        return action, max(0, min(n - 1, int(prog * n)))
    now = _clock_ms()
    off = _stance_of(char) * 400                      # desync folk
    per = _LOOP_PERIOD.get(action, 1500)
    return action, int(((now + off) / per) * n) % n


_HELM = {"warrior", "guard", "paladin", "knight", "fighter", "soldier"}
_HAT = {"wizard", "sorcerer", "warlock", "mage", "necromancer"}
_HOOD = {"rogue", "ranger", "druid", "assassin", "thief", "monk", "cultist"}
_CIRCLET = {"noble", "king", "queen", "lord", "lady", "prince", "princess"}


def _headgear_for(char):
    klass = getattr(getattr(char, "character_class", None), "value", "")
    if klass in _HELM:
        return "helmet"
    if klass in _HAT:
        return "hat"
    if klass in _HOOD:
        return "hood"
    if klass in _CIRCLET:
        return "circlet"
    return None


def kit_of(char):
    """ISO.12 the worn GEAR as a hashable tuple (weapon, head, shield, height):
    the equipped weapon KIND, class headgear, a shield flag, and the body-type
    height — so a warrior reads a helmet + sword + shield, a wizard a hat + staff,
    a ranger a hood + bow."""
    from ui import char_motion, iso_skeleton
    try:
        weapon = char_motion.weapon_kind(char)
        shield = char_motion.has_shield(char)
    except Exception:
        weapon, shield = None, False
    height = iso_skeleton.body_of(char)[1]
    return (weapon, _headgear_for(char), bool(shield), height)


def char_sprite(char, size: int, facing=None):
    # facing: None → read the character's movement; an int → a legacy 0-7 octant
    delta = _DELTAS[int(facing) % 8] if facing is not None else move_delta(char)
    from ui import iso_skeleton
    angle = iso_skeleton.angle_for_delta(*delta)      # ISO.9 face where you move
    tint, hair = _tint(char), _hair(char)
    action, frame = _frame_state(char)
    build = iso_skeleton.build_of(char)               # ISO.7 silhouette variety
    seed = _stance_of(char)                            # ISO.11 idle/dance variety
    kit = kit_of(char)                                 # ISO.12 weapon/armour/body
    style, seq = None, 0
    if action == "attack":                             # ISO.13/COMBAT.1 strikes
        anim = (getattr(char, "metadata", {}) or {}).get("_anim", {})
        style = anim.get("atk_style", "overhead")
        seq = int(anim.get("atk_seen", 0) or 0)        # rotate the repertoire
    key = (tint, hair, size, delta, action, frame, build, seed, kit, style, seq)
    if key not in _CACHE:
        phase = frame / _frames_of(action)
        # ISO.6: a real Mixamo-mocap-driven rigged skeleton; if the clip is
        # missing, fall back to the ISO.3/4 procedural box figure.
        mesh = iso_skeleton.sample_figure(action, phase, tint, hair, angle,
                                          build, seed, kit, style, seq)
        cam = iso_skeleton.CAM
        if mesh is None:
            mesh = _figure(tint, hair, angle, _stance_of(char), action, phase)
            cam = _CHAR_CAM
        _CACHE[key] = r3.bake(mesh, size=size, **cam)
    return _CACHE[key]
