"""Procedural body renderer for characters.

Adapted from autonomous_world/game/ui/character_anim.py + character_detail.py,
condensed for our smaller tile size.

Each NPC is drawn as a small jointed figure with:
- Head (race-tinted skin color, ears for elf/orc/etc.)
- Torso (class-tinted)
- Two legs that swing with `walk_phase` while moving
- Two arms (one may hold a weapon)
- Optional weapon overlay (sword/bow/staff)
- Optional death overlay (fades to red on the ground)

Animation state lives on the character in `metadata['_anim']`:
    {'walk_phase': float, 'idle_phase': float,
     'prev_pos': (x, y), 'moving': bool}

Frame-rate independent: callers pass `dt` and the renderer advances state.
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
    "halfling": 0.78,
    "gnome": 0.78,
    "goblin": 0.78,
    "dwarf": 0.88,
    "human": 1.0,
    "elf": 1.0,
    "half-elf": 1.0,
    "tiefling": 1.0,
    "dragonborn": 1.10,
    "half-orc": 1.10,
    "orc": 1.15,
    "troll": 1.30,
}

# Class -> weapon kind drawn in the hand. None means unarmed.
CLASS_WEAPON = {
    "warrior": "sword",
    "guard": "sword",
    "paladin": "sword",
    "barbarian": "axe",
    "rogue": "dagger",
    "ranger": "bow",
    "wizard": "staff",
    "sorcerer": "staff",
    "warlock": "staff",
    "cleric": "mace",
    "druid": "staff",
    "monk": "staff",
    "noble": "dagger",
    "brigand": "axe",
    "troll": "axe",
    "merchant": None,
    "villager": None,
    "bard": "dagger",
    "monster": None,
}


# ---------------------------------------------------------------------- helpers

def _race_color(race: str) -> Tuple[int, int, int]:
    return SKIN_TONES.get((race or "").lower(), (210, 185, 155))


def _class_color(klass: str) -> Tuple[int, int, int]:
    return CLASS_TORSO_TINT.get((klass or "").lower(), (170, 160, 130))


def _race_scale(race: str) -> float:
    return RACE_SCALE.get((race or "").lower(), 1.0)


def _darken(color, amount=30):
    return tuple(max(0, c - amount) for c in color)


def _ensure_anim(char) -> dict:
    meta = getattr(char, "metadata", None)
    if not isinstance(meta, dict):
        meta = {}
        char.metadata = meta
    anim = meta.get("_anim")
    if not isinstance(anim, dict):
        anim = {
            "walk_phase": 0.0,
            "idle_phase": 0.0,
            "prev_pos": tuple(char.position),
            "moving": False,
            "facing": (0, 1),
            "atk_t": 0.0,
            "atk_seen": None,
        }
        meta["_anim"] = anim
    return anim


def update_anim(char, dt: float) -> None:
    """Advance walk/idle phases, facing, and the strike timer (P33.4)."""
    from ui import char_motion
    anim = _ensure_anim(char)
    prev = anim["prev_pos"]
    cur = tuple(char.position)
    moving = prev != cur
    if moving:
        char_motion.update_facing(anim, prev, cur)
    anim["prev_pos"] = cur
    anim["moving"] = moving
    if moving:
        anim["walk_phase"] = (anim["walk_phase"] + dt * 8.0) % math.tau
    else:
        anim["walk_phase"] *= 0.9
        anim["idle_phase"] = (anim["idle_phase"] + dt * 1.5) % math.tau
    # strike lunge: the engine bumps metadata['_atk_seq']; run a real-time timer
    seq = (getattr(char, "metadata", None) or {}).get("_atk_seq", 0)
    if seq != anim.get("atk_seen"):
        if anim.get("atk_seen") is not None:
            anim["atk_t"] = char_motion.ATTACK_DUR
        anim["atk_seen"] = seq
    elif anim.get("atk_t", 0) > 0:
        anim["atk_t"] = max(0.0, anim["atk_t"] - dt)


# ---------------------------------------------------------------------- main draw

def draw_body(surface, char, sx: int, sy: int, tile_size: int,
              is_player: bool = False) -> None:
    """Draw a single character at screen pixel (sx, sy)."""
    if not PYGAME_OK:
        return
    anim = _ensure_anim(char)
    if not char.is_alive():
        _draw_corpse(surface, char, sx, sy, tile_size)
        return

    from ui import char_motion
    race = getattr(char.race, "value", "human")
    klass = getattr(char.character_class, "value", "villager")
    skin = _race_color(race)
    torso_color = char_motion.armor_tint(char, _class_color(klass))
    scale = _race_scale(race) * (tile_size / 32.0)

    # Layout coordinates within the tile (centered)
    cx = sx + tile_size // 2
    cy = sy + tile_size // 2
    # a strike leans the whole figure toward what it's hitting (P33.4)
    lunge = char_motion.attack_lunge(anim.get("atk_t", 0.0))
    fx, fy = char_motion.facing(anim)
    lean_x, lean_y = int(fx * lunge * 3), int(fy * lunge * 2)
    head_r = max(3, int(5 * scale))
    body_w = max(6, int(10 * scale))
    body_h = max(7, int(11 * scale))
    leg_h = max(4, int(6 * scale))
    arm_l = max(4, int(6 * scale))

    walk = anim["walk_phase"]
    idle = anim["idle_phase"]
    sway = math.sin(walk) if anim["moving"] else math.sin(idle) * 0.25

    # Shadow
    shadow = pygame.Surface((body_w + 4, leg_h // 2 + 2), pygame.SRCALPHA)
    pygame.draw.ellipse(shadow, (0, 0, 0, 90), shadow.get_rect())
    surface.blit(shadow, (cx - (body_w + 4) // 2,
                          cy + body_h // 2 + 1))
    cx += lean_x                       # the body leans; the shadow stayed put
    cy += lean_y

    # Legs
    leg_offset = int(sway * 2)
    left_leg_x = cx - body_w // 3
    right_leg_x = cx + body_w // 3
    leg_y = cy + body_h // 2 - 1
    pygame.draw.rect(surface, _darken(torso_color, 60),
                     (left_leg_x - 1, leg_y - leg_offset, 2, leg_h))
    pygame.draw.rect(surface, _darken(torso_color, 60),
                     (right_leg_x - 1, leg_y + leg_offset, 2, leg_h))

    # Torso
    pygame.draw.rect(surface, torso_color,
                     (cx - body_w // 2, cy - body_h // 2 + 1,
                      body_w, body_h), border_radius=2)
    pygame.draw.rect(surface, _darken(torso_color, 40),
                     (cx - body_w // 2, cy - body_h // 2 + 1,
                      body_w, body_h), 1, border_radius=2)

    # Arms (one may carry a weapon)
    arm_swing = int(sway * 2)
    left_arm_x = cx - body_w // 2 - 1
    right_arm_x = cx + body_w // 2 + 1
    arm_top_y = cy - body_h // 4
    pygame.draw.line(surface, torso_color,
                     (left_arm_x, arm_top_y),
                     (left_arm_x - 2, arm_top_y + arm_l - arm_swing), 2)
    pygame.draw.line(surface, torso_color,
                     (right_arm_x, arm_top_y),
                     (right_arm_x + 2, arm_top_y + arm_l + arm_swing), 2)

    # Head
    head_x = cx
    head_y = cy - body_h // 2 - head_r + 1
    head_y += int(math.sin(idle * 0.7) * 1) if not anim["moving"] else 0
    pygame.draw.circle(surface, skin, (head_x, head_y), head_r)
    pygame.draw.circle(surface, _darken(skin, 50),
                       (head_x, head_y), head_r, 1)

    # Race-specific ears (elf / half-elf / orc / goblin / half-orc)
    if race in ("elf", "half-elf"):
        pygame.draw.polygon(surface, skin, [
            (head_x - head_r, head_y),
            (head_x - head_r - 2, head_y - 1),
            (head_x - head_r, head_y + 1),
        ])
        pygame.draw.polygon(surface, skin, [
            (head_x + head_r, head_y),
            (head_x + head_r + 2, head_y - 1),
            (head_x + head_r, head_y + 1),
        ])
    elif race in ("orc", "half-orc", "goblin"):
        # Tusks
        pygame.draw.line(surface, (220, 220, 200),
                         (head_x - 1, head_y + head_r - 1),
                         (head_x - 1, head_y + head_r + 1), 1)
        pygame.draw.line(surface, (220, 220, 200),
                         (head_x + 1, head_y + head_r - 1),
                         (head_x + 1, head_y + head_r + 1), 1)
    elif race == "troll":
        # Larger head, greenish ridge
        pygame.draw.circle(surface, _darken(skin, 40),
                           (head_x, head_y - head_r // 2),
                           max(1, head_r // 3))

    # Eyes
    eye_y = head_y - 1
    pygame.draw.rect(surface, (30, 30, 30),
                     (head_x - 2, eye_y, 1, 1))
    pygame.draw.rect(surface, (30, 30, 30),
                     (head_x + 1, eye_y, 1, 1))

    # Weapon — what the character ACTUALLY wields (P33.4), not just its class
    weapon = char_motion.weapon_kind(char)
    if weapon:
        _draw_weapon(surface, weapon, right_arm_x + 2,
                     arm_top_y + arm_l + arm_swing, scale)

    # Player crown
    if is_player:
        pygame.draw.polygon(surface, (255, 220, 80), [
            (head_x - head_r + 1, head_y - head_r - 1),
            (head_x - head_r // 2, head_y - head_r - 3),
            (head_x, head_y - head_r - 1),
            (head_x + head_r // 2, head_y - head_r - 3),
            (head_x + head_r - 1, head_y - head_r - 1),
        ])

    # HP indicator (small bar above) for non-players
    if not is_player and char.max_hp > 0 and char.hp < char.max_hp:
        bw = max(4, body_w + 2)
        bh = 2
        bx = cx - bw // 2
        by = head_y - head_r - 4
        pygame.draw.rect(surface, (60, 0, 0), (bx, by, bw, bh))
        ratio = max(0.0, char.hp / char.max_hp)
        pygame.draw.rect(surface, (200, 50, 50),
                         (bx, by, int(bw * ratio), bh))


def draw_glimpsed(surface, char, sx: int, sy: int, tile_size: int,
                  is_player: bool = False) -> None:
    """Draw a character SEEN THROUGH A WINDOW (P14.2) — dimmed and behind a
    faint pane — so an NPC glimpsed inside a building reads as indoors
    rather than standing on top of the wall. Reuses `draw_body` on a
    scratch tile, then knocks its alpha down and glazes it."""
    if not PYGAME_OK:
        return
    glass = pygame.Surface((tile_size, tile_size), pygame.SRCALPHA)
    draw_body(glass, char, 0, 0, tile_size)
    glass.fill((255, 255, 255, 135), special_flags=pygame.BLEND_RGBA_MULT)
    surface.blit(glass, (sx, sy))
    pane = pygame.Surface((tile_size, tile_size), pygame.SRCALPHA)
    pygame.draw.rect(pane, (140, 170, 205, 70), pane.get_rect(),
                     max(1, tile_size // 16))
    surface.blit(pane, (sx, sy))


def _draw_weapon(surface, weapon: str, x: int, y: int, scale: float) -> None:
    s = max(1.0, scale)
    if weapon == "sword":
        pygame.draw.line(surface, (220, 220, 230),
                         (x, y), (x + 2, y - int(8 * s)), 2)
        pygame.draw.line(surface, (160, 110, 60),
                         (x - 1, y - 1), (x + 2, y - 1), 2)
    elif weapon == "axe":
        pygame.draw.line(surface, (140, 100, 70),
                         (x, y), (x + 2, y - int(8 * s)), 2)
        pygame.draw.polygon(surface, (200, 200, 210), [
            (x + 2, y - int(8 * s)),
            (x + int(5 * s), y - int(7 * s)),
            (x + 2, y - int(5 * s)),
        ])
    elif weapon == "dagger":
        pygame.draw.line(surface, (220, 220, 230),
                         (x, y), (x + 1, y - int(4 * s)), 2)
    elif weapon == "bow":
        pygame.draw.arc(surface, (140, 90, 50),
                        (x, y - int(8 * s), int(6 * s), int(10 * s)),
                        -math.pi / 2, math.pi / 2, 2)
        pygame.draw.line(surface, (220, 220, 200),
                         (x + 1, y - int(6 * s)),
                         (x + 1, y - 1), 1)
    elif weapon == "staff":
        pygame.draw.line(surface, (110, 80, 50),
                         (x, y), (x + 1, y - int(10 * s)), 2)
        pygame.draw.circle(surface, (120, 180, 255),
                           (x + 1, y - int(10 * s)), 2)
    elif weapon == "mace":
        pygame.draw.line(surface, (140, 90, 50),
                         (x, y), (x + 1, y - int(7 * s)), 2)
        pygame.draw.circle(surface, (180, 180, 200),
                           (x + 1, y - int(8 * s)), 2)


def _draw_corpse(surface, char, sx: int, sy: int, tile_size: int) -> None:
    cx = sx + tile_size // 2
    cy = sy + tile_size // 2 + 2
    w = tile_size // 2
    h = max(2, tile_size // 5)
    pygame.draw.ellipse(surface, (90, 30, 30), (cx - w // 2, cy, w, h))
    pygame.draw.ellipse(surface, (50, 10, 10),
                        (cx - w // 2, cy, w, h), 1)


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
