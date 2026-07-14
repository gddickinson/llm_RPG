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
        anim = {
            "walk_phase": 0.0, "idle_phase": 0.0,
            "prev_pos": tuple(char.position), "moving": False,
            "facing": (0, 1), "atk_t": 0.0, "atk_seen": None,
            "tween_from": (0, 0), "tween_t": 0.0,
        }
        meta["_anim"] = anim
    return anim


TWEEN_DUR = 0.16           # seconds to slide from the old tile to the new one
CHAR_H_FRAC = 1.5          # a character stands this many tiles tall (overflows up)


def update_anim(char, dt: float) -> None:
    """Advance walk/idle phases, facing, the tile-to-tile TWEEN, and the strike
    timer (P33.4b). The tween is what makes the walk cycle VISIBLE — a turn-based
    step teleports tiles, so we slide the sprite across and play the walk."""
    from ui import char_motion
    anim = _ensure_anim(char)
    prev = anim["prev_pos"]
    cur = tuple(char.position)
    if prev != cur:                        # a step: start a slide from prev→cur
        char_motion.update_facing(anim, prev, cur)
        anim["tween_from"] = (prev[0] - cur[0], prev[1] - cur[1])
        anim["tween_t"] = TWEEN_DUR
    anim["prev_pos"] = cur
    tweening = anim.get("tween_t", 0.0) > 0
    anim["moving"] = tweening
    if tweening:
        anim["walk_phase"] = (anim["walk_phase"] + dt * 20.0) % math.tau
        anim["tween_t"] = max(0.0, anim["tween_t"] - dt)
    else:
        anim["walk_phase"] *= 0.85
        anim["idle_phase"] = (anim["idle_phase"] + dt * 1.6) % math.tau
    seq = (getattr(char, "metadata", None) or {}).get("_atk_seq", 0)
    if seq != anim.get("atk_seen"):
        if anim.get("atk_seen") is not None:
            anim["atk_t"] = char_motion.ATTACK_DUR
        anim["atk_seen"] = seq
    elif anim.get("atk_t", 0) > 0:
        anim["atk_t"] = max(0.0, anim["atk_t"] - dt)
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
    if anim.get("action_t", 0) > 0:
        anim["cur_action"] = anim.get("action", "idle")
    elif anim.get("atk_t", 0) > 0:
        anim["cur_action"] = "attack"
    elif meta.get("_stance"):
        anim["cur_action"] = meta["_stance"]
    elif anim.get("moving"):
        anim["cur_action"] = "run" if meta.get("_running") else "walk"
    else:
        anim["cur_action"] = "idle"


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
    from ui import char_motion, char_pose, body_parts as bp

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
        # ease the slide (slow-in/out) instead of a linear crawl (P34.1)
        frac = 1.0 - smoothstep(1.0 - tw / TWEEN_DUR)
        ox, oy = fdx * tile_size * frac, fdy * tile_size * frac
    feet_x = sx + tile_size / 2 + ox
    feet_y = sy + tile_size - 2 + oy

    atk_t = anim.get("atk_t", 0.0)
    attack = 1.0 - atk_t / char_motion.ATTACK_DUR if atk_t > 0 else 0.0
    facing = char_motion.facing(anim)
    pose = char_pose.build_pose(feet_x, feet_y, H, anim.get("walk_phase", 0.0),
                                anim.get("idle_phase", 0.0),
                                anim.get("moving", False), attack, facing, build)
    # apply the current ACTION clip (jump/sit/bow/wave/guard/hurt/…) (P33.6b)
    from ui import char_clips
    action = anim.get("cur_action", "idle")
    if char_clips.is_one_shot(action) and anim.get("action_dur"):
        phase = 1.0 - anim.get("action_t", 0.0) / anim["action_dur"]
    else:
        phase = anim.get("clock", 0.0)
    pose = char_clips.apply(action, pose, phase, H, facing)

    # shadow on the ground, under the feet (not the tweened body)
    shw = max(4, int(H * 0.26))
    shadow = pygame.Surface((shw, max(2, shw // 2)), pygame.SRCALPHA)
    pygame.draw.ellipse(shadow, (0, 0, 0, 95), shadow.get_rect())
    surface.blit(shadow, (int(sx + tile_size / 2 - shw / 2),
                          int(sy + tile_size - shw / 2 - 1)))

    leg_w = max(2, int(H * 0.10))
    arm_w = max(2, int(H * 0.075))
    neck_w = max(2, int(H * 0.06))
    face_visible = facing[1] >= 0

    bp.draw_legs(surface, pose, pants, boots, leg_w)
    if char_motion.has_shield(char):
        bp.draw_shield(surface, pose, (120, 110, 95), (88, 76, 60),
                       max(2, int(H * 0.13)))
    bp.draw_torso(surface, pose, torso, belt)
    bp.draw_arms(surface, pose, torso, skin, arm_w)
    bp.draw_head(surface, pose, skin, hair, race, face_visible, neck_w,
                 pose.get("profile", 0))
    weapon = char_motion.weapon_kind(char)
    if weapon:
        bp.draw_weapon(surface, weapon, pose, H * 0.42, arm_w)

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


def draw_glimpsed(surface, char, sx: int, sy: int, tile_size: int,
                  is_player: bool = False) -> None:
    """Draw a character SEEN THROUGH A WINDOW (P14.2) — dimmed and behind a
    faint pane — so an NPC glimpsed inside a building reads as indoors rather
    than standing on top of the wall. Reuses `draw_body` on a taller scratch
    surface (the body overflows the tile), then glazes it."""
    if not PYGAME_OK:
        return
    pad = tile_size                          # room for the overflowing body
    glass = pygame.Surface((tile_size, tile_size + pad), pygame.SRCALPHA)
    draw_body(glass, char, 0, pad, tile_size)
    glass.fill((255, 255, 255, 135), special_flags=pygame.BLEND_RGBA_MULT)
    surface.blit(glass, (sx, sy - pad))
    pane = pygame.Surface((tile_size, tile_size), pygame.SRCALPHA)
    pygame.draw.rect(pane, (140, 170, 205, 70), pane.get_rect(),
                     max(1, tile_size // 16))
    surface.blit(pane, (sx, sy))


def _draw_corpse(surface, char, sx: int, sy: int, tile_size: int) -> None:
    cx = sx + tile_size // 2
    cy = sy + tile_size // 2 + 2
    w = tile_size // 2
    h = max(2, tile_size // 5)
    pygame.draw.ellipse(surface, (90, 30, 30), (cx - w // 2, cy, w, h))
    pygame.draw.ellipse(surface, (50, 10, 10), (cx - w // 2, cy, w, h), 1)


# ---------------------------------------------------------------------- projectile sprite

def draw_projectile(surface, kind: str, sx: int, sy: int,
                    tile_size: int) -> None:
    """Draw an in-flight projectile sprite (called by the map renderer)."""
    if not PYGAME_OK:
        return
    cx = sx + tile_size // 2
    cy = sy + tile_size // 2
    if kind == "arrow":
        pygame.draw.line(surface, (200, 170, 110),
                         (cx - 4, cy), (cx + 4, cy), 2)
        pygame.draw.polygon(surface, (220, 220, 230),
                            [(cx + 4, cy - 2), (cx + 7, cy), (cx + 4, cy + 2)])
    elif kind == "bolt":
        pygame.draw.line(surface, (160, 160, 170),
                         (cx - 3, cy), (cx + 5, cy), 3)
    elif kind == "stone":
        pygame.draw.circle(surface, (140, 130, 120), (cx, cy), 3)
    elif kind == "spell":
        pygame.draw.circle(surface, (200, 160, 255), (cx, cy), 4)
        pygame.draw.circle(surface, (255, 220, 255), (cx, cy), 2)
    else:
        pygame.draw.circle(surface, (240, 240, 200), (cx, cy), 3)
