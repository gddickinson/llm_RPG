"""P33.4 character motion & equipment — pure helpers for the body renderer.

The old body renderer chose the drawn weapon from a character's CLASS and never
animated a strike. This module reads what a character ACTUALLY wields and wears
and turns an attack counter into a lunge — all pure and headless-testable;
`body_renderer` blits the result.

Attack animation is driven counter-style so the engine stays pygame-free:
`combat_system` bumps `metadata['_atk_seq']` when a character strikes; the
renderer notices the change in `update_anim` (which has a real-time `dt`) and
runs a short lunge timer. No game logic ever touches a clock.
"""

import math

ATTACK_DUR = 0.32          # seconds a strike animation runs

# weapon name/id keyword → the drawn category (order matters: specific first)
WEAPON_KEYWORDS = [
    ("crossbow", "bow"), ("longbow", "bow"), ("shortbow", "bow"),
    ("bow", "bow"), ("sling", "bow"),
    ("dagger", "dagger"), ("knife", "dagger"), ("dirk", "dagger"),
    ("greatsword", "sword"), ("longsword", "sword"), ("scimitar", "sword"),
    ("rapier", "sword"), ("sabre", "sword"), ("sword", "sword"),
    ("blade", "sword"), ("katana", "sword"),
    ("greataxe", "axe"), ("battleaxe", "axe"), ("axe", "axe"),
    ("hatchet", "axe"), ("halberd", "spear"), ("glaive", "spear"),
    ("spear", "spear"), ("pike", "spear"), ("lance", "spear"),
    ("trident", "spear"),
    ("warhammer", "mace"), ("hammer", "mace"), ("maul", "mace"),
    ("mace", "mace"), ("club", "mace"), ("flail", "mace"), ("morningstar", "mace"),
    ("quarterstaff", "staff"), ("staff", "staff"), ("wand", "staff"),
    ("rod", "staff"), ("scepter", "staff"),
]

# armour name/id keyword → a torso tint (metal / leather); else keep the base
_METAL = ("plate", "chain", "mail", "steel", "iron", "scale", "brigandine")
_LEATHER = ("leather", "hide", "studded", "padded")
METAL_TINT = (172, 176, 186)
LEATHER_TINT = (120, 86, 56)


def _worn(char, slot):
    try:
        from characters.equipment import get_equipment
        return get_equipment(char).get(slot)
    except Exception:
        return None


def _tag(item) -> str:
    return (getattr(item, "id", "") + " " + getattr(item, "name", "")).lower()


def weapon_kind(char):
    """The weapon category to DRAW: read the WORN weapon and classify it by
    name (else its `weapon_kind`); fall back to the character's class default;
    None if truly unarmed."""
    w = _worn(char, "weapon")
    if w is not None:
        tag = _tag(w)
        for key, cat in WEAPON_KEYWORDS:
            if key in tag:
                return cat
        wk = getattr(w, "weapon_kind", "")
        if wk == "ranged":
            return "bow"
        if wk == "magic":
            return "staff"
        return "sword"                      # a generic melee blade
    from ui.body_renderer import CLASS_WEAPON
    klass = getattr(getattr(char, "character_class", None), "value", "")
    return CLASS_WEAPON.get(klass)


def armor_tint(char, base):
    """Nudge the torso colour toward the WORN armour material (metal / leather)
    so a plated knight reads as steel and a scout as leather."""
    a = _worn(char, "armor")
    if a is None:
        return base
    tag = _tag(a)
    if any(k in tag for k in _METAL):
        return METAL_TINT
    if any(k in tag for k in _LEATHER):
        return LEATHER_TINT
    return base


def has_shield(char) -> bool:
    return _worn(char, "shield") is not None


def attack_lunge(t, dur=ATTACK_DUR):
    """0..1 lunge magnitude over a strike: thrust out (peak mid) then ease
    back. `t` counts DOWN from `dur` to 0."""
    if t <= 0 or dur <= 0:
        return 0.0
    p = max(0.0, min(1.0, 1.0 - t / dur))
    return math.sin(p * math.pi)


def update_facing(anim, prev, cur):
    """Store the last movement direction as the sprite's facing."""
    dx, dy = cur[0] - prev[0], cur[1] - prev[1]
    if dx or dy:
        anim["facing"] = ((dx > 0) - (dx < 0), (dy > 0) - (dy < 0))


def facing(anim):
    return anim.get("facing", (0, 1))       # default: facing the camera (south)


# ---- P33.6b action / emote API (engine-facing, pygame-free) ------------

def emote(char, name):
    """Request a one-shot animation clip (bow / wave / jump / cheer / hurt /
    cast / stoop / leap …). The renderer plays it next frame."""
    try:
        char.metadata["_emote"] = name
    except Exception:
        pass


def set_stance(char, stance):
    """Hold a looping stance (sit / guard / sleep / dance), or None to clear."""
    try:
        if stance:
            char.metadata["_stance"] = stance
        else:
            char.metadata.pop("_stance", None)
    except Exception:
        pass


def face_toward(char, target_pos):
    """Turn the character to face a tile it's interacting with / fighting."""
    try:
        px, py = char.position
        dx, dy = target_pos[0] - px, target_pos[1] - py
        if dx or dy:
            if abs(dx) >= abs(dy):
                char.metadata["_face"] = (1 if dx > 0 else -1, 0)
            else:
                char.metadata["_face"] = (0, 1 if dy > 0 else -1)
    except Exception:
        pass
