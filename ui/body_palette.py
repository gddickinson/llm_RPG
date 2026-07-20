"""Character palettes + pure colour/build helpers (split from `body_renderer` to
hold the 500-line line, T0.3). Skin/class/hair colours, race scale, per-person
build, and small colour math. Pure — no pygame. `body_renderer` re-imports these,
so `from ui.body_renderer import CLASS_WEAPON` (etc.) still resolves."""

import math
from typing import Tuple

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

# H4 population variety — a per-person HAIRSTYLE (short weighted common), seeded
# off the id but decorrelated from the hair-colour hash so both vary independently
_HAIR_STYLES = ("short", "short", "short", "long", "bun", "bald")

# P33.6a per-character BUILD — diverse, slightly cartoonish silhouettes
_BUILDS = [
    {"shoulder": 1.0, "hip": 1.0, "head": 1.0, "girth": 1.0, "h": 1.0},      # average
    {"shoulder": 1.3, "hip": 1.05, "head": 0.95, "girth": 1.25, "h": 1.02},  # broad
    {"shoulder": 0.85, "hip": 0.85, "head": 1.05, "girth": 0.8, "h": 1.05},  # slim
    {"shoulder": 1.05, "hip": 1.25, "head": 1.0, "girth": 1.4, "h": 0.92},   # round
    {"shoulder": 0.95, "hip": 0.9, "head": 0.92, "girth": 0.9, "h": 1.12},   # tall
    {"shoulder": 1.1, "hip": 1.1, "head": 1.15, "girth": 1.15, "h": 0.84},   # short
]


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


def _hair_style(char):
    h = 0                                        # a spreading hash (sum clusters)
    for c in str(getattr(char, "id", "x")):
        h = (h * 131 + ord(c)) & 0x7fffffff
    return _HAIR_STYLES[h % len(_HAIR_STYLES)]


def _body_build(char):
    """A stable per-character build (average/broad/slim/round/tall/short)."""
    h = sum(ord(c) for c in str(getattr(char, "id", "x"))) + 3
    return _BUILDS[h % len(_BUILDS)]
