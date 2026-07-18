"""Procedural body renderer for characters (P33.4b — jointed & feet-anchored).

A character is drawn as a JOINTED figure that stands ~1.5 tiles tall, anchored at
the feet and overflowing UPWARD so it reads big without shrinking the map. The
skeleton (joint positions) comes from the pure `char_pose` module; the limbs /
torso / head / weapon are blitted by `body_parts`; this file is the orchestration
— palettes, animation state, and the draw order.

Animation state lives on the character in `metadata['_anim']` and is advanced by
`update_anim(char, dt)` each frame: a walk cycle (visible because a tile step is
TWEENED across, `tween_t`), an idle breath, 4-way facing, and a strike swing.
Equipment (the drawn weapon/armour) is resolved by `char_motion`.
"""

import logging
import math
from typing import Tuple

try:
    import pygame
    PYGAME_OK = True
except ImportError:  # pragma: no cover
    PYGAME_OK = False

logger = logging.getLogger("llm_rpg.body_renderer")


# ---------------------------------------------------------------------- palettes

SKIN_TONES = {
    "human": (210, 185, 155),
    "elf": (220, 205, 175),
    "half-elf": (215, 195, 165),
    "dwarf": (195, 165, 130),
    "halfling": (215, 190, 155),
    "gnome": (210, 195, 165),
    "half-orc": (140, 160, 120),
    "orc": (120, 145, 100),
    "tiefling": (180, 130, 130),
    "goblin": (130, 150, 90),
    "dragonborn": (160, 170, 150),
    "troll": (90, 130, 70),
}

CLASS_TORSO_TINT = {
    "warrior": (170, 175, 185),
    "guard": (150, 155, 165),
    "paladin": (190, 195, 210),
    "barbarian": (140, 120, 100),
    "ranger": (100, 130, 90),
    "rogue": (70, 70, 80),
    "merchant": (160, 140, 60),
    "villager": (150, 130, 90),
    "wizard": (90, 70, 140),
    "sorcerer": (180, 70, 160),
    "warlock": (110, 50, 130),
    "cleric": (220, 220, 220),
    "druid": (90, 130, 70),
    "bard": (180, 100, 160),
    "monk": (140, 130, 110),
    "noble": (120, 90, 160),
    "brigand": (110, 70, 50),
    "troll": (110, 140, 80),
    "monster": (140, 100, 100),
}

RACE_SCALE = {
    "halfling": 0.82, "gnome": 0.82, "goblin": 0.82, "dwarf": 0.90,
    "human": 1.0, "elf": 1.02, "half-elf": 1.0, "tiefling": 1.0,
    "dragonborn": 1.08, "half-orc": 1.10, "orc": 1.14, "troll": 1.28,
}

# Class -> weapon kind drawn in the hand when nothing is equipped. None = unarmed.
CLASS_WEAPON = {
    "warrior": "sword", "guard": "sword", "paladin": "sword",
    "barbarian": "axe", "rogue": "dagger", "ranger": "bow", "wizard": "staff",
    "sorcerer": "staff", "warlock": "staff", "cleric": "mace", "druid": "staff",
    "monk": "staff", "noble": "dagger", "brigand": "axe", "troll": "axe",
    "merchant": None, "villager": None, "bard": "dagger", "monster": None,
}

# I1 social-contact clips that busy both hands — no weapon/shield is brandished
# through them (an embrace / clasp / kiss reads wrong with a raised sword).
_EMPTY_HANDED = {"handshake", "hug", "kiss"}

HAIR_PALETTE = [(58, 40, 26), (30, 26, 24), (120, 90, 52), (150, 122, 74),
                (162, 162, 168), (110, 62, 36), (92, 74, 58)]


# ---------------------------------------------------------------------- helpers

def _race_color(race: str) -> Tuple[int, int, int]:
    return SKIN_TONES.get((race or "").lower(), (210, 185, 155))


def _class_color(klass: str) -> Tuple[int, int, int]:
    return CLASS_TORSO_TINT.get((klass or "").lower(), (170, 160, 130))


def _race_scale(race: str) -> float:
    return RACE_SCALE.get((race or "").lower(), 1.0)


def _darken(color, amount=30):
    return tuple(max(0, c - amount) for c in color)


def _cap(x, y, tx, ty, cap):
    """Clamp a sprung point to within `cap` px of its target: a follow-through lag
    may settle but can NEVER detach a limb — the guard that stops any large
    screen-space jump (a camera pan / a move between locations) from smearing."""
    dx, dy = x - tx, y - ty
    d = math.hypot(dx, dy)
    if d > cap > 0:
        s = cap / d
        return tx + dx * s, ty + dy * s
    return x, y


def _hair_color(char):
    race = getattr(getattr(char, "race", None), "value", "human")
    if race in ("orc", "half-orc", "goblin", "troll"):
        return (44, 50, 34)
    h = sum(ord(c) for c in str(getattr(char, "id", "x")))
    return HAIR_PALETTE[h % len(HAIR_PALETTE)]


# P33.6a per-character BUILD — diverse, slightly cartoonish silhouettes
_BUILDS = [
    {"shoulder": 1.0, "hip": 1.0, "head": 1.0, "girth": 1.0, "h": 1.0},    # average
    {"shoulder": 1.3, "hip": 1.05, "head": 0.95, "girth": 1.25, "h": 1.02},  # broad
    {"shoulder": 0.85, "hip": 0.85, "head": 1.05, "girth": 0.8, "h": 1.05},  # slim
    {"shoulder": 1.05, "hip": 1.25, "head": 1.0, "girth": 1.4, "h": 0.92},  # round
    {"shoulder": 0.95, "hip": 0.9, "head": 0.92, "girth": 0.9, "h": 1.12},  # tall
    {"shoulder": 1.1, "hip": 1.1, "head": 1.15, "girth": 1.15, "h": 0.84},  # short
]


def _body_build(char):
    """A stable per-character build (average/broad/slim/round/tall/short)."""
    h = sum(ord(c) for c in str(getattr(char, "id", "x"))) + 3
    return _BUILDS[h % len(_BUILDS)]


def _ensure_anim(char) -> dict:
    meta = getattr(char, "metadata", None)
    if not isinstance(meta, dict):
        meta = {}
        char.metadata = meta
    anim = meta.get("_anim")
    if not isinstance(anim, dict):
        # P34.4 individuality: seed the idle breath PHASE + SPEED from the id so a
        # crowd never breathes in lockstep (each body has its own rhythm).
        seed = sum(ord(c) for c in str(getattr(char, "id", "x")))
        anim = {
            "walk_phase": 0.0,
            "idle_phase": (seed % 100) / 100.0 * math.tau,
            "idle_rate": 0.80 + (seed % 11) / 11.0 * 0.5,     # 0.80–1.30×
            "prev_pos": tuple(char.position), "moving": False,
            "facing": (0, 1), "atk_t": 0.0, "atk_seen": None,
            "tween_from": (0, 0), "tween_t": 0.0,
        }
        meta["_anim"] = anim
    return anim


# continuous tile-to-tile motion lives in char_tween (shared with the iso path);
# re-exported here for back-compat (iso_actors imports TWEEN_DUR from body_renderer)
from ui.char_tween import (TWEEN_DUR, NPC_TWEEN_MAX, STRIDE_PER_TILE,  # noqa: F401
                           start_slide as _start_slide,
                           advance_slide as _advance_slide)
CHAR_H_FRAC = 1.5          # a character stands this many tiles tall (overflows up)


def update_anim(char, dt: float, is_player: bool = False) -> None:
    """Advance walk/idle phases, facing, the tile-to-tile TWEEN, and the strike
    timer (P33.4b). The tween is what makes the walk cycle VISIBLE — a turn-based
    step teleports tiles, so we slide the sprite across and play the walk. An
    NPC's slide fills the gap since its last step (continuous ambient motion); the
    player keeps the crisp fixed `TWEEN_DUR` so input stays responsive."""
    from ui import char_motion
    anim = _ensure_anim(char)
    anim["since_move"] = anim.get("since_move", 0.0) + dt
    prev = anim["prev_pos"]
    cur = tuple(char.position)
    if prev != cur:                        # a step: start a slide from prev→cur
        char_motion.update_facing(anim, prev, cur)
        from ui.char_pose3d import facing_from_delta
        anim["face_target"] = facing_from_delta(cur[0] - prev[0],
                                                cur[1] - prev[1])
        _start_slide(anim, prev, cur, is_player)
    anim["prev_pos"] = cur
    # ease the continuous facing angle toward the heading (P34.14) — the cast
    # TURNS to face any of 360° instead of snapping to 4 views
    tgt = anim.get("face_target")
    if tgt is not None:
        cur_a = anim.get("face_cur", tgt)
        d = ((tgt - cur_a + 180) % 360) - 180
        anim["face_cur"] = (cur_a + d * min(1.0, dt * 9.0)) % 360.0
    tweening = anim.get("tween_t", 0.0) > 0
    anim["moving"] = tweening
    if tweening:
        _advance_slide(anim, dt)           # stride + tween timers a frame
    else:
        anim["walk_phase"] *= 0.85
        anim["idle_phase"] = (anim["idle_phase"]
                              + dt * 1.6 * anim.get("idle_rate", 1.0)) % math.tau
    seq = (getattr(char, "metadata", None) or {}).get("_atk_seq", 0)
    if seq != anim.get("atk_seen"):
        if anim.get("atk_seen") is not None:
            anim["atk_t"] = char_motion.ATTACK_DUR
            # P34.11b rotate through the character's strike repertoire so a fight
            # varies swing-to-swing (a combo), not the same blow every time
            from ui import char_style
            vs = char_style.attack_variants(char, char_motion.weapon_kind(char))
            anim["atk_style"] = vs[seq % len(vs)]
        anim["atk_seen"] = seq
    elif anim.get("atk_t", 0) > 0:
        anim["atk_t"] = max(0.0, anim["atk_t"] - dt)
    from ui import char_face
    seed = sum(ord(c) for c in str(getattr(char, "id", "x")))
    char_face.blink_step(anim, dt, seed)
    # look-at: ease a head/eye offset toward a point of interest (P34.3)
    from ui import char_secondary as cs
    sec = anim.setdefault("_sec", {})
    tgt = (getattr(char, "metadata", None) or {}).get("_look")
    want = cs.look_dir(char.position, tgt) if tgt else (0.0, 0.0)
    sec["look"] = cs.ease2(sec.get("look", (0.0, 0.0)), want, 0.12)
    _update_action(char, anim, dt)


def _update_action(char, anim, dt):
    """P33.6b action state machine: pick the current clip (a one-shot emote, an
    attack, a held stance, walk/run, or idle) and advance its clock."""
    from ui import char_clips
    meta = getattr(char, "metadata", None) or {}
    anim["clock"] = anim.get("clock", 0.0) + dt
    face = meta.pop("_face", None)
    if face:
        anim["facing"] = tuple(face)
        from ui.char_pose3d import facing_from_delta
        anim["face_target"] = facing_from_delta(face[0], face[1])
    bq = meta.pop("_bubble", None)                 # emote-bubble request (P34.2)
    if not bq and meta.get("_stance") == "sleep":
        bq = "sleep"
    if bq:
        anim["bubble"] = bq
        anim["bubble_t"] = 1.6
    elif anim.get("bubble_t", 0) > 0:
        anim["bubble_t"] = max(0.0, anim["bubble_t"] - dt)
    if anim.get("action_t", 0) > 0:
        anim["action_t"] = max(0.0, anim["action_t"] - dt)
    req = meta.pop("_emote", None)
    if req:
        name = req if isinstance(req, str) else req[0]
        # a one-shot may start when nothing is playing; a HURT always cuts in
        if char_clips.is_one_shot(name) and (anim.get("action_t", 0) <= 0
                                             or name == "hurt"):
            anim["action"] = name
            anim["action_dur"] = char_clips.duration(name) or 0.6
            anim["action_t"] = anim["action_dur"]
    mode = meta.get("_move_mode")                  # P34.12 walk / jog / crawl
    if anim.get("action_t", 0) > 0:
        anim["cur_action"] = anim.get("action", "idle")
    elif anim.get("atk_t", 0) > 0:
        anim["cur_action"] = "attack"
    elif meta.get("_stance"):
        anim["cur_action"] = meta["_stance"]
    elif mode == "crawl":                          # prone, whether moving or not
        anim["cur_action"] = "crawl"
    elif anim.get("moving"):
        anim["cur_action"] = ("run" if meta.get("_running")
                              else "jog" if mode == "jog" else "walk")
    else:
        anim["cur_action"] = "idle"


def _draw_ground_shadow(surface, pose, feet_x, feet_y, H) -> None:
    """R6 — a soft contact shadow on the ground under the feet: directional (cast
    down-right, away from the top-left key light), pose-shaped (wider on a spread
    stance) and height-aware (it SHRINKS + fades as the body lifts off the ground
    on a jump or a launch, so airborne reads). Concentric fading ellipses on one
    small SRCALPHA surface → soft edge, one blit."""
    lf, rf = pose.get("l_foot"), pose.get("r_foot")
    if lf and rf:
        spread = abs(lf[0] - rf[0])
        pfy = (lf[1] + rf[1]) * 0.5
    else:
        spread, pfy = 0.0, feet_y
    lift = feet_y - pfy if feet_y > pfy else 0.0        # airborne height
    scale = max(0.4, 1.0 - lift / (H * 1.3)) if H else 1.0
    ew = max(4, int((H * 0.30 + spread * 0.7) * scale))
    eh = max(2, int(ew * 0.42))
    sh = pygame.Surface((ew, eh), pygame.SRCALPHA)
    base_a = int(96 * scale)
    rings = 4
    for i in range(rings, 0, -1):
        f = i / rings                                   # 1 = outer/faint … dark
        a = max(0, int(base_a * (1.0 - f) ** 1.05) + 6)
        rw, rh = ew * f, eh * f
        pygame.draw.ellipse(sh, (0, 0, 0, a),
                            ((ew - rw) * 0.5, (eh - rh) * 0.5, rw, rh))
    cx = feet_x + H * 0.05                               # down-right of the feet
    cy = feet_y + H * 0.02
    surface.blit(sh, (int(cx - ew * 0.5), int(cy - eh * 0.5)))


# ---------------------------------------------------------------------- main draw

def draw_body(surface, char, sx: int, sy: int, tile_size: int,
              is_player: bool = False) -> None:
    """Draw a jointed, feet-anchored character (overflows its tile so it reads
    big), posed and animated by `char_pose` + `body_parts` (P33.4b)."""
    if not PYGAME_OK:
        return
    anim = _ensure_anim(char)
    if not char.is_alive():
        _draw_corpse(surface, char, sx, sy, tile_size)
        return
    # P34.18 non-humanoids (wolves, boars, slimes, wisps…) get their own body plan;
    # goblins/trolls/orcs/skeletons/bandits stay on the jointed puppet below
    from ui import creature_pose
    plan = creature_pose.body_plan(char)
    if plan != "humanoid":
        from ui import creature_render
        creature_render.draw_creature(surface, char, sx, sy, tile_size, plan,
                                      is_player)
        return
    from ui import char_motion, body_parts as bp

    race = getattr(char.race, "value", "human")
    klass = getattr(char.character_class, "value", "villager")
    skin = _race_color(race)
    torso = char_motion.armor_tint(char, _class_color(klass))
    pants = _darken(torso, 48)
    boots = (58, 44, 34)
    hair = _hair_color(char)
    belt = (74, 52, 34)

    build = _body_build(char)
    H = int(tile_size * CHAR_H_FRAC * _race_scale(race) * build["h"])
    # feet anchored at the tile's bottom-centre + the tween slide from the old tile
    ox = oy = 0.0
    tw = anim.get("tween_t", 0.0)
    if tw > 0:
        from ui.animation import smoothstep
        fdx, fdy = anim.get("tween_from", (0, 0))
        dur = anim.get("tween_dur", TWEEN_DUR) or TWEEN_DUR
        # ease the slide (slow-in/out) instead of a linear crawl (P34.1)
        frac = 1.0 - smoothstep(1.0 - tw / dur)
        ox, oy = fdx * tile_size * frac, fdy * tile_size * frac
    atk_t = anim.get("atk_t", 0.0)
    attack = 1.0 - atk_t / char_motion.ATTACK_DUR if atk_t > 0 else 0.0
    if atk_t > 0:                          # G3: a strike LUNGES the whole body
        # toward the target — so the attack reads from ANY facing, not just the
        # arm arc (which is near-invisible head-on)
        lunge = char_motion.attack_lunge(atk_t) * tile_size * 0.17
        lfx, lfy = char_motion.facing(anim)
        ox += lfx * lunge
        oy += lfy * lunge
    feet_x = sx + tile_size / 2 + ox
    feet_y = sy + tile_size - 2 + oy

    from ui import char_clips, char_style, char_pose3d, char_mocap, char_injury
    action = anim.get("cur_action", "idle")
    weapon = char_motion.weapon_kind(char)
    # I1: a warm social-contact clip busies BOTH hands (an embrace, a clasp, a
    # kiss) — don't brandish a weapon or shield through it, or a hug reads as a
    # sword raised.  A square-up (taunt) keeps its arms, so it stays armed.
    bare_hands = action in _EMPTY_HANDED
    inj = char_injury.injury_state(char)          # P34.17 injuries show
    if inj["down"]:                               # unconscious / dying → lie downed
        action = "lie"
    elif (char.metadata or {}).get("_fx_fire", 0) > 0 and \
            action in ("idle", "walk", "run", "jog"):
        action = "flail"                          # P34.19 on fire → panic flail
    # P34.11 per-character motion style: a gait (walk/run varies), a melee attack
    # style (by weapon then id) and a cast gesture — so the cast reads as individuals
    gait = char_style.gait_of(char)
    astyle = anim.get("atk_style") or char_style.attack_style(char, weapon)
    pgait = gait
    if action == "run":                          # a run has a longer, springier gait
        pgait = {"stride": gait["stride"] * 1.4, "bob": gait["bob"] * 1.25,
                 "arm": gait["arm"] * 1.3, "cadence": gait["cadence"]}
    # P34.14 CONTINUOUS FACING: project the body skeleton at the eased heading angle
    # (front → ¾ → side → back, any direction the character moves), then apply the
    # action clip on top. Replaces the 4-view build_pose/mocap split. P34.6 adds a
    # mood-driven line-of-action spine curve (proud arch / sad slump).
    from ui import char_face
    mood = char_face.EMOTE_EXPR.get(action) or char_face.expr_for(char)
    if mood == "neutral":                        # G1: a badly-hurt body winces
        try:
            if char.is_alive() and char.hp <= max(1, char.max_hp) * 0.25:
                mood = "hurt"
        except Exception:
            pass
    spine = char_pose3d.spine_for(mood)
    face_deg = anim.get("face_cur", 0.0)
    # P34.15 LOCOMOTION plays baked MOCAP through the depth model (real stride/timing
    # at any facing); everything else is the procedural pose + its action clip.
    loco = char_mocap.clip_for(action) if action in ("walk", "run", "idle") else None
    # COMBAT.1 the 2D renderer plays the real combat + DEFENCE mocap too (an
    # attack rotates the weapon's repertoire, a block/dodge/hit plays its
    # capture); everything else stays the procedural pose below.
    mclip, mp = loco, None
    if loco:
        if action in ("walk", "run", "jog"):
            # tie the stride to ground speed (`move_phase` advances with the
            # tween) so the walk cycle flows with the glide, not a fixed clock
            mp = anim.get("move_phase", 0.0) * gait["cadence"]
        else:
            mp = (anim.get("clock", 0.0) * char_mocap.RATE.get(loco, 1.0)
                  * gait["cadence"])
    else:
        cm = char_mocap.combat_mocap(action, anim, weapon, attack)
        if cm:
            mclip, mp = cm
    if mclip:
        pose = char_pose3d.pose3d_mocap(feet_x, feet_y, H, mclip, mp, face_deg,
                                        build, pgait, spine)
        facing = pose["facing"]
    else:
        pose = char_pose3d.pose3d(feet_x, feet_y, H, anim.get("walk_phase", 0.0),
                                  face_deg, build, anim.get("moving", False),
                                  attack, astyle, pgait,
                                  anim.get("idle_phase", 0.0), spine)
        facing = pose["facing"]
        if char_clips.is_one_shot(action) and anim.get("action_dur"):
            phase = 1.0 - anim.get("action_t", 0.0) / anim["action_dur"]
        else:
            phase = anim.get("clock", 0.0)
        clip_action = (char_style.cast_style(char, weapon)
                       if action == "cast" else action)
        pose = char_clips.apply(clip_action, pose, phase, H, facing)

    if not inj["down"]:                           # P34.17 limp + a limp arm
        if inj["limp"] and action in ("walk", "run", "jog"):
            char_injury.apply_limp(pose, anim.get("walk_phase", 0.0), H,
                                   inj["limp"])
        if inj["arm"]:
            char_injury.apply_arm(pose, inj["arm"], H)

    # R6 grounding — a soft, directional, pose-shaped contact shadow under the
    # feet (cast down-right from the top-left key light; wider on a spread stance;
    # SHRINKS + fades as the body lifts off the ground on a jump / a launch)
    _draw_ground_shadow(surface, pose, feet_x, feet_y, H)

    # P34.3 secondary motion in BODY-LOCAL space: the head lags the body and the
    # weapon tip whips behind a swing (follow-through / settle). The spring works
    # on OFFSETS from a STATIC tile anchor (no camera scroll, no tween slide), so a
    # camera pan or a jump BETWEEN LOCATIONS shifts the anchor and the pose in
    # lock-step and never reaches the spring — only the body's own motion does.
    # Offsets are capped, so a lag can settle but never detach a limb.
    from ui import char_secondary as cs
    sec = anim.setdefault("_sec", {})
    ax = sx + tile_size / 2.0
    ay = sy + tile_size - 2.0
    lx, ly = sec.get("look", (0.0, 0.0))
    htx = pose["head"][0] - ax + lx * H * 0.05
    hty = pose["head"][1] - ay + ly * H * 0.05
    hx, hy, hvx, hvy = sec.get("head", (htx, hty, 0.0, 0.0))
    hx, hy, hvx, hvy = cs.spring2(hx, hy, hvx, hvy, htx, hty, 1 / 30.0,
                                  cs.HEAD_STIFF)
    hx, hy = _cap(hx, hy, htx, hty, H * 0.10)
    sec["head"] = (hx, hy, hvx, hvy)
    pose["head"] = (ax + hx, ay + hy)
    wtx = pose["r_hand"][0] - ax
    wty = pose["r_hand"][1] - ay
    wx, wy, wvx, wvy = sec.get("weap", (wtx, wty, 0.0, 0.0))
    wx, wy, wvx, wvy = cs.spring2(wx, wy, wvx, wvy, wtx, wty, 1 / 30.0,
                                  cs.WEAP_STIFF)
    wx, wy = _cap(wx, wy, wtx, wty, H * 0.16)
    sec["weap"] = (wx, wy, wvx, wvy)
    pose["r_hand"] = (ax + wx, ay + wy)

    leg_w = max(2, int(H * 0.10))
    arm_w = max(2, int(H * 0.075))
    neck_w = max(2, int(H * 0.06))
    face_visible = pose.get("face_visible", facing[1] >= 0)

    # P34.5 flow: a billowing cloak + swaying hair BEHIND the body
    from ui import char_flow
    cloak_color = (_darken(torso, 55) if klass.lower() in char_flow.CLOAK_CLASSES
                   else None)
    char_flow.draw_back(surface, char, anim, pose, sx, sy, tile_size, H, hair,
                        cloak_color)

    # P34.14 depth-sort: the arm farther from the camera is drawn BEHIND the
    # torso (and dimmed for depth); the near arm in front — so a ¾/back view reads
    depth = pose.get("cam_depth", {})
    far = "l" if depth.get("l_sh", 0.0) <= depth.get("r_sh", 0.0) else "r"
    near = "r" if far == "l" else "l"
    bp.draw_legs(surface, pose, pants, boots, leg_w)
    if klass.lower() in bp.ROBE_CLASSES:         # R5: a robe hangs over the legs
        bp.draw_robe(surface, pose, torso, max(3, int(H * 0.05)))
    bp.draw_arm(surface, pose, far, _darken(torso, 26), _darken(skin, 26), arm_w)
    if char_motion.has_shield(char) and not bare_hands:
        bp.draw_shield(surface, pose, (120, 110, 95), (88, 76, 60),
                       max(2, int(H * 0.13)))
    bp.draw_torso(surface, pose, torso, belt)
    bp.draw_arm(surface, pose, near, torso, skin, arm_w)
    kl = klass.lower()
    if kl in bp.ARMOR_CLASSES:                    # G5 armored shoulder plates
        bp.draw_pauldrons(surface, pose, bp._lighten(torso, 22),
                          max(2, int(H * 0.09)))
    if kl in bp.HOOD_CLASSES:                     # G5 a cowl behind the head
        bp.draw_hood(surface, pose, _darken(torso, 28), max(3, int(H * 0.09)))
    expr = mood                    # resolved above (fleeting action face / mood)
    bp.draw_head(surface, pose, skin, hair, race, face_visible, neck_w,
                 pose.get("profile", 0), expr, anim.get("blinking", False),
                 sec.get("look", (0.0, 0.0)))
    if weapon and not bare_hands:                # resolved above (P34.11)
        bp.draw_weapon(surface, weapon, pose, H * 0.42, arm_w)
    char_flow.draw_front(surface, anim, pose, sx, sy, tile_size, atk_t, weapon)

    hx, hy = int(pose["head"][0]), int(pose["head"][1])
    hr = pose["head_r"]
    if is_player:
        pygame.draw.polygon(surface, (255, 220, 80), [
            (hx - hr, hy - hr - 1), (hx - hr // 2, hy - hr - hr),
            (hx, hy - hr - 1), (hx + hr // 2, hy - hr - hr),
            (hx + hr, hy - hr - 1)])
    if not is_player and char.max_hp > 0 and char.hp < char.max_hp:
        bw = max(6, int(H * 0.30))
        bx, by = hx - bw // 2, hy - hr - 4
        pygame.draw.rect(surface, (60, 0, 0), (bx, by, bw, 2))
        pygame.draw.rect(surface, (200, 50, 50),
                         (bx, by, int(bw * max(0.0, char.hp / char.max_hp)), 2))
    if anim.get("bubble_t", 0) > 0 and anim.get("bubble"):   # emote bubble (P34.2)
        bp.draw_bubble(surface, hx, hy - hr - 3, anim["bubble"], hr)
    from ui import char_fx                        # P34.19 fire / wet overlays
    char_fx.draw_effects(surface, char, sx, sy, tile_size, anim.get("clock", 0.0))


SSAA_SCALE = 2                 # P34.7 oversample factor for crisp, anti-aliased art


def _draw_corpse(surface, char, sx: int, sy: int, tile_size: int) -> None:
    cx = sx + tile_size // 2
    cy = sy + tile_size // 2 + 2
    w = tile_size // 2
    h = max(2, tile_size // 5)
    pygame.draw.ellipse(surface, (90, 30, 30), (cx - w // 2, cy, w, h))
    pygame.draw.ellipse(surface, (50, 10, 10), (cx - w // 2, cy, w, h), 1)


# draw_body_crisp / draw_glimpsed / draw_projectile moved to ui/body_draw.py
# (500-line line); re-exported here so existing imports keep working.
from ui.body_draw import (draw_body_crisp, draw_glimpsed,   # noqa: E402,F401
                          draw_projectile)
