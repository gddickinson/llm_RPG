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

# ISO.11 the game action → the Mixamo mocap clip that reads it (18 clips ship in
# data/anim/*.json). ATTACK has no sword-swing clip so it rides the idle base + a
# procedural weapon-arm ARC overlay; SWIM is procedural (see swim_figure).
_CLIP = {
    "idle": "idle", "walk": "walk", "jog": "walk", "run": "run",
    "sneak": "walk", "attack": "idle",
    "dance": "dance", "sit": "sit", "sleep": "sit", "stoop": "sit",
    "crawl": "sit", "climb": "climb", "talk": "talk", "wave": "talk",
    "cast": "talk", "argue": "argue", "guard": "idle", "bow": "nod",
    "cheer": "hiphop", "jump": "jump", "leap": "jump", "hurt": "stagger",
    "dodge": "stagger", "stagger": "stagger", "kick": "kick",
    # ISO.13 ambient gestures (the P34.4 idle-life fidgets) so idle folk LIVE
    "shrug": "talk", "ponder": "nod", "yawn": "idle", "stretch": "climb",
    "reach": "climb", "salute": "talk", "beckon": "talk", "facepalm": "talk",
    "clap": "argue", "laugh": "argue", "point": "talk", "nod": "nod",
    "kneel": "sit", "winded": "stagger", "cast_point": "talk",
    "cast_staff": "talk",
}
# ISO.11 per-character VARIETY: a seeded idle/dance picks one of the Mixamo
# variants so a crowd doesn't loop in lockstep.
_IDLE_VARIANTS = ("idle", "idle2", "idle3")
_DANCE_VARIANTS = ("dance", "breakdance", "hiphop")

# a camera framing the ~1.6-unit skeleton (tuned in the ISO.6 prototype)
CAM = dict(cam_pos=(2.1, 2.5, -2.5), look=(0.0, 0.78, 0.0), vfov_deg=30.0)

_LEGJ = ("_hip", "_knee", "_foot")
_ARMJ = ("_sh", "_elbow", "_hand")


def clip_for(action: str, seed: int = 0) -> str:
    """The mocap clip for a game action; a `seed` (per-character) varies the
    idle/dance so folk don't loop in lockstep (ISO.11)."""
    if action == "idle":
        return _IDLE_VARIANTS[seed % 3]
    if action == "dance":
        return _DANCE_VARIANTS[seed % 3]
    return _CLIP.get(action, "idle")


# ---- ISO.9 facing calibration ------------------------------------------
# The skeleton is rotated by an angle about the vertical, then baked through
# the FIXED perspective CAM. Because that camera is tilted, the body's forward
# (+z) projects to a screen direction that is a NON-LINEAR function of the
# rotation (perspective foreshortening) — so rotating by the raw world azimuth
# (the ISO.7 bug) pointed the figure the wrong way. We instead CALIBRATE: for a
# world move (dx,dy) whose iso-screen direction is (dx-dy, dx+dy), find the
# rotation whose forward projects to that same screen direction.

def _fwd_screen_angle(a: float) -> float:
    """Screen direction (radians, y-DOWN) the body-forward (+z) projects to at
    skeleton rotation `a`, through CAM (matches `raster3d.render`'s projection).
    """
    cam = np.array(CAM["cam_pos"], float)
    fwd = np.array(CAM["look"], float) - cam
    fwd /= (np.linalg.norm(fwd) or 1.0)
    right = np.cross(fwd, np.array([0.0, 1.0, 0.0]))
    right /= (np.linalg.norm(right) or 1.0)
    upv = np.cross(right, fwd)
    thf = math.tan(math.radians(CAM["vfov_deg"]) / 2.0)

    def scr(p):
        rel = np.asarray(p, float) - cam
        zc = rel @ fwd
        return np.array([(rel @ right) / (zc * thf), -(rel @ upv) / (zc * thf)])

    base = np.array([0.0, 1.0, 0.0])
    tip = base + 0.5 * np.array([math.sin(a), 0.0, math.cos(a)])
    d = scr(tip) - scr(base)
    return math.atan2(d[1], d[0])


_FACE_TABLE = None


def _face_table():
    global _FACE_TABLE
    if _FACE_TABLE is None:
        _FACE_TABLE = [(_fwd_screen_angle(math.radians(a)), math.radians(a))
                       for a in range(0, 360, 2)]
    return _FACE_TABLE


def angle_for_delta(dx: float, dy: float) -> float:
    """The skeleton rotation (radians) that makes the figure FACE the world
    movement (dx,dy) as seen in the iso view — inverts the camera's perspective
    foreshortening so the character strides the way it actually moves."""
    if dx == 0 and dy == 0:
        dx, dy = 0, 1                                 # still → face the camera
    want = math.atan2(dx + dy, dx - dy)               # iso-screen dir (y-down)

    def ad(x, y):
        d = abs(x - y) % (2 * math.pi)
        return min(d, 2 * math.pi - d)

    return min(_face_table(), key=lambda t: ad(t[0], want))[1]


def _seed_of(char) -> int:
    h = 0
    for ch in (getattr(char, "id", "") or getattr(char, "name", "") or "x"):
        h = (h * 131 + ord(ch)) & 0x7fffffff
    return h


def body_of(char):
    """ISO.12 a stable per-person BODY TYPE (shoulder breadth, overall height)
    seeded off the id, so a crowd has slight/broad + short/tall folk — different
    body types with no sex field on Character."""
    h = _seed_of(char)
    shoulder = (0.86, 1.0, 1.15)[h % 3]
    height = (0.92, 1.0, 1.08)[(h // 3) % 3]
    return shoulder, height


def build_of(char) -> float:
    """ISO.7 the shoulder-breadth factor (see body_of)."""
    return body_of(char)[0]


def _lat(j: str, build: float = 1.0) -> float:
    if j[:2] in ("l_", "r_"):
        side = -1.0 if j.startswith("l_") else 1.0
        if any(j.endswith(s) for s in _LEGJ):
            return side * _HIP_W * (1.0 + (build - 1.0) * 0.4)   # hips vary less
        if any(j.endswith(s) for s in _ARMJ):
            return side * _SH_W * build                          # shoulders vary
    return 0.0


def pose3d(pose_norm, angle, build: float = 1.0) -> dict:
    """{joint: (x,y,z)} — lateral spread (scaled by the person's `build`) +
    height + fore-aft depth, rotated by `angle` radians about the vertical
    (ISO.7 continuous 360° facing)."""
    out = {j: np.array([_lat(j, build), ny * _H, nx * _D])
           for j, (nx, ny) in pose_norm.items()}
    out["pelvis"] = (out["l_hip"] + out["r_hip"]) / 2.0
    c, s = math.cos(angle), math.sin(angle)
    rot = np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])
    return {k: rot @ v for k, v in out.items()}


_EYE = (34, 28, 26)


def _apply_height(P, kit):
    if kit and len(kit) > 3 and kit[3] != 1.0:            # ISO.12 body height
        return {k: v * np.array([1.0, kit[3], 1.0]) for k, v in P.items()}
    return P


def _build(P, tint, hair, angle, kit):
    """Body mesh + worn gear from a (possibly transformed) joint dict `P`."""
    m = _body(P, tint, hair, angle)
    if kit and any(kit[:3]):                              # ISO.12 worn gear
        from ui import iso_gear
        m += iso_gear.accessories(P, angle, kit)
    return m


def figure(pose_norm, tint, hair, angle, build: float = 1.0, kit=None):
    """ISO.10/12 — a believable low-poly BODY over the mocap joints (tapered
    limbs, ball joints, hands, booted feet, a tunic torso + belt, a shaped head
    with hair + a face), plus the person's HEIGHT and worn GEAR (weapon / shield
    / headgear) from `kit`. Faces `angle` with the `build` (shoulder breadth)."""
    P = _apply_height(pose3d(pose_norm, angle, build), kit)
    return _build(P, tint, hair, angle, kit)


def _rot_about(v, piv, axis, ang):
    """Rotate point `v` by `ang` about `axis` through `piv` (Rodrigues)."""
    axis = axis / (np.linalg.norm(axis) or 1.0)
    d = v - piv
    c, s = math.cos(ang), math.sin(ang)
    return piv + d * c + np.cross(axis, d) * s + axis * np.dot(axis, d) * (1 - c)


def _swing_arm(P, style, phase, angle):
    """ISO.13 a real 3D weapon-arm SWING — a distinct move per style: an OVERHEAD
    chop (up-back → down-front), a horizontal SLASH sweeping across the body, or
    a forward THRUST/stab. The weapon (attached at r_hand) follows the swing."""
    fwd = np.array([math.sin(angle), 0.0, math.cos(angle)])
    rt = np.array([math.cos(angle), 0.0, -math.sin(angle)])
    up = np.array([0.0, 1.0, 0.0])
    P = dict(P)
    sh = P["r_sh"]
    if style == "thrust":
        ext = math.sin(phase * math.pi) * 0.42
        P["r_elbow"] = P["r_elbow"] + fwd * ext * 0.5 + up * 0.06
        P["r_hand"] = P["r_hand"] + fwd * ext + up * 0.12
        return P
    if style == "slash":
        a = math.radians(95 - 180 * phase)               # right → across → left
        axis = up
    else:                                                # overhead (default)
        a = math.radians(-95 + 185 * phase)              # raised → chop down
        axis = rt
    for j in ("r_elbow", "r_hand"):
        P[j] = _rot_about(P[j], sh, axis, a)
    P["r_elbow"] = P["r_elbow"] + up * 0.05              # clear the body
    return P


def attack_figure(phase, style, tint, hair, angle, build, kit):
    """ISO.13 the figure mid-STRIKE — the idle base with a 3D `style` swing."""
    P = _apply_height(pose3d(cm.sample_norm("idle", 0.0), angle, build), kit)
    P = _swing_arm(P, style or "overhead", phase, angle)
    return _build(P, tint, hair, angle, kit)


def _body(P, tint, hair, angle):
    """Build the body mesh from a joint dict `P` (ISO.11 split so a pose can be
    pitched — e.g. SWIM — before the mesh is laid over it)."""
    tunic = tuple(int(x) for x in tint)
    sleeve = tuple(int(c * 0.9) for c in tunic)
    boot = tuple(int(c * 0.55) for c in _LEG)
    belt = tuple(int(c * 0.5) for c in tunic)
    hair = tuple(int(x) for x in hair)
    fwd = np.array([math.sin(angle), 0.0, math.cos(angle)])   # facing forward
    rt = np.array([math.cos(angle), 0.0, -math.sin(angle)])   # facing right
    # segs tuned for a good look at a modest triangle budget (baked once/cached):
    # tapered limbs seg 6, joints seg 5, the prominent head seg 7, tiny face 4
    m = []
    # ISO.13 slimmer, more athletic proportions (was blockier). legs — thigh +
    # shin taper to a ball knee, a booted foot, a hip ball
    for s in ("l_", "r_"):
        hip, kn, ft = P[s + "hip"], P[s + "knee"], P[s + "foot"]
        m += [r3.taper(hip, kn, 0.09, 0.062, _LEG, 6), r3.ball(kn, 0.06, _LEG, 5),
              r3.taper(kn, ft, 0.062, 0.046, _LEG, 6), r3.ball(hip, 0.082, tunic, 5),
              r3.box(ft[0] + fwd[0] * 0.05, ft[1] - 0.02, ft[2] + fwd[2] * 0.05,
                     0.1, 0.055, 0.24, boot)]
    # torso — a narrower waist tapering to squarer shoulders, chest, neck, belt
    pel, chest, neck = P["pelvis"], P["chest"], P["neck"]
    m += [r3.taper(pel, chest, 0.122, 0.168, tunic, 7),
          r3.ball(chest, 0.1, tunic, 6),
          r3.taper(chest, neck, 0.092, 0.058, tunic, 6),
          r3.taper(pel + np.array([0, -0.02, 0]), pel + np.array([0, 0.04, 0]),
                   0.128, 0.128, belt, 7)]
    # arms — a slim shoulder, sleeved upper arm, elbow, bare forearm + a hand
    for s in ("l_", "r_"):
        sh, el, ha = P[s + "sh"], P[s + "elbow"], P[s + "hand"]
        m += [r3.ball(sh, 0.05, tunic, 5), r3.taper(sh, el, 0.048, 0.04, sleeve, 6),
              r3.ball(el, 0.039, sleeve, 4), r3.taper(el, ha, 0.04, 0.031, _SKIN, 5),
              r3.ball(ha, 0.043, _SKIN, 5)]
    # neck + head + hair cap + a face (two eyes, a nose)
    m.append(r3.taper(neck, neck + np.array([0, 0.07, 0]), 0.046, 0.05, _SKIN, 5))
    hc = P["head"] + np.array([0, -0.01, 0])
    m += [r3.ball(hc, 0.112, _SKIN, 7),
          r3.ball(hc + np.array([0, 0.045, 0]) - fwd * 0.02, 0.115, hair, 6)]
    for sgn in (-1, 1):
        m.append(r3.ball(hc + fwd * 0.098 + rt * 0.043 * sgn
                         + np.array([0, 0.012, 0]), 0.019, _EYE, 4))
    m.append(r3.ball(hc + fwd * 0.112 + np.array([0, -0.02, 0]), 0.021, _SKIN, 4))
    return m


def swim_figure(phase, tint, hair, angle, build: float = 1.0, kit=None):
    """ISO.11 procedural SWIM (no Mixamo swim clip): the climb clip drives an
    arm-over-arm STROKE, and the whole body is PITCHED to horizontal about the
    pelvis and dropped to lie at the water surface — a front crawl. Headgear
    rides along; a weapon/shield is stowed while swimming."""
    pose = cm.sample_norm("climb", phase)
    if pose is None:
        return None
    P = pose3d(pose, angle, build)
    piv = P["pelvis"].copy()
    c, s = math.cos(math.radians(74)), math.sin(math.radians(74))
    rot = np.array([[1, 0, 0], [0, c, -s], [0, s, c]])   # pitch fore-aft
    P = {k: rot @ (v - piv) + piv for k, v in P.items()}
    lift = 0.28 - min(float(v[1]) for v in P.values())   # lie ~at the surface
    P = {k: v + np.array([0.0, lift, 0.0]) for k, v in P.items()}
    try:
        m = _body(P, tint, hair, angle)
        if kit and kit[1]:                               # keep the headgear on
            from ui import iso_gear
            m += iso_gear.headgear_mesh(
                kit[1], P["head"] + np.array([0.0, -0.01, 0.0]),
                np.array([math.sin(angle), 0.0, math.cos(angle)]))
        return m
    except Exception:
        return None


def sample_figure(action, phase, tint, hair, angle, build: float = 1.0, seed=0,
                  kit=None, style=None):
    """The body mesh for `action` at `phase` facing `angle` radians (with the
    person's `build` + worn `kit`), or None if the clip is missing (caller falls
    back to the box figure). SWIM is procedural; ATTACK is a 3D `style` swing."""
    if action == "swim":
        return swim_figure(phase, tint, hair, angle, build, kit)
    if action == "attack":
        try:
            return attack_figure(phase, style, tint, hair, angle, build, kit)
        except Exception:
            return None
    pose = cm.sample_norm(clip_for(action, seed), phase)
    if pose is None:
        return None
    try:
        return figure(pose, tint, hair, angle, build, kit)
    except Exception:
        return None
