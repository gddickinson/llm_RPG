"""P34.11 per-character MOTION STYLE (pure) — variety in the common actions.

So the cast doesn't all move, fight and cast identically, each character gets a
stable GAIT (stride / bob / arm-swing / cadence), a melee ATTACK STYLE (overhead /
thrust / slash, by weapon then id) and a CAST STYLE — all seeded from `char.id`, so
a crowd reads as individuals. Consumed by `body_renderer` (→ `char_pose.build_pose`
gait + attack_style, mocap cadence, and the cast-clip choice). Headless-testable.
"""


def _seed(char):
    return sum(ord(c) for c in str(getattr(char, "id", "x")))


# gait presets — multipliers on the walk/run stride, vertical bob, arm swing and
# the mocap cadence (walk-cycle speed). Index 0 is the neutral reference.
_GAITS = [
    {"stride": 1.00, "bob": 1.00, "arm": 1.00, "cadence": 1.00},   # even
    {"stride": 1.28, "bob": 1.20, "arm": 1.35, "cadence": 0.90},   # long, loping
    {"stride": 0.78, "bob": 0.70, "arm": 0.72, "cadence": 1.20},   # short, quick
    {"stride": 1.05, "bob": 1.50, "arm": 1.10, "cadence": 1.05},   # springy bounce
    {"stride": 0.95, "bob": 0.85, "arm": 1.60, "cadence": 0.98},   # big arm swing
    {"stride": 1.15, "bob": 0.90, "arm": 0.85, "cadence": 1.12},   # brisk strider
]

# weapon → a fixed melee flavour (else the id decides for variety)
_WEAPON_STYLE = {
    "axe": "overhead", "mace": "overhead", "hammer": "overhead",
    "dagger": "thrust", "spear": "thrust", "staff": "thrust",
}
_MELEE_POOL = ("overhead", "slash", "thrust")


def gait_of(char):
    """A stable per-character gait (stride/bob/arm/cadence multipliers)."""
    return _GAITS[(_seed(char) + 2) % len(_GAITS)]


def attack_style(char, weapon):
    """How this character swings: forced by heavy/pointy weapons, else by id."""
    forced = _WEAPON_STYLE.get((weapon or "").lower())
    if forced:
        return forced
    return _MELEE_POOL[_seed(char) % len(_MELEE_POOL)]


def cast_style(char, weapon):
    """Which casting gesture: a staff-wielder slams, others point or two-hand."""
    if (weapon or "").lower() == "staff":
        return "cast_staff"
    return "cast" if _seed(char) % 2 == 0 else "cast_point"
