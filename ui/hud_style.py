"""HUD styling (P15.3) — the pure colour logic behind the log & minimap.

Two visual jobs, both really just "given this line / this tile-state,
what colour?", pulled out of the HUD so they can be unit-tested (the
`ui/animation.py` move):

  * `line_color(text)` — the event log is prefix-coded and those
    prefixes are load-bearing ([DM], [Law], [!], …). Colour each line by
    its prefix, falling back to the SEMANTIC category (`event_filter`'s
    single-source `categorize`) for the unprefixed lines, so combat runs
    orange, ambient chatter dims, your own acts stay neutral.

  * `dim` / `fog_terrain_color` — the minimap should obey the P15.11 fog
    of war like the main map does: full colour where you can see, dim
    where you've only been, dark where you never have.
"""

from engine.event_filter import categorize

# The iconic prefixes get crisp, distinct hues (the plan's [Law] gold,
# [DM] violet, [!] red — plus the rest of the load-bearing family).
PREFIX_COLORS = {
    "[!]": (235, 70, 60),           # danger — red
    "[Law]": (240, 205, 90),        # bounty / crime — gold
    "[Clash]": (235, 120, 80),      # a street fight — orange-red
    "[DM]": (190, 140, 240),        # the Dungeon Master — violet
    "[Realm]": (170, 160, 240),     # world news — blue-violet
    "[Board]": (150, 200, 240),     # the quest board — sky
    "[Legend]": (230, 190, 120),    # relic lore — amber
    "[Collection]": (120, 220, 200),
    "[Topic]": (200, 200, 150),
    "[Lesson]": (160, 220, 160),
    "[Bond]": (150, 220, 160),      # trust minted — green
    "[Secret]": (200, 160, 220),    # a secret told — orchid
    "[Home]": (200, 175, 120),      # your homestead — tan
    "[Overnight]": (150, 160, 200),
}

# Fallback by semantic category for lines that carry no prefix.
CATEGORY_COLORS = {
    "critical": (235, 70, 60),
    "combat": (240, 150, 90),       # hits / damage — orange
    "news": (190, 140, 240),
    "law": (240, 205, 90),
    "social": (150, 220, 160),
    "player": (220, 220, 220),      # your deliberate acts — neutral
    "ambient": (150, 150, 165),     # footsteps / barks — dim grey
}
DEFAULT_LOG = (220, 220, 220)

# minimap fog
UNSEEN = (16, 16, 20)               # never visited — near-black
EXPLORED_DIM = 0.5                  # remembered ground — half-lit


def line_color(text) -> tuple:
    """The colour one event-log line should render in."""
    try:
        t = str(text).strip()
    except Exception:
        return DEFAULT_LOG
    for pfx, col in PREFIX_COLORS.items():
        if t.startswith(pfx):
            return col
    try:
        return CATEGORY_COLORS.get(categorize(t), DEFAULT_LOG)
    except Exception:
        return DEFAULT_LOG


def dim(color, factor: float = EXPLORED_DIM) -> tuple:
    """Scale an RGB toward black (clamped)."""
    return tuple(max(0, min(255, int(c * factor))) for c in color[:3])


def fog_terrain_color(base, visible: bool, explored: bool) -> tuple:
    """The colour a minimap tile shows given its fog state: full where
    visible, dimmed where only explored, near-black where unseen."""
    if visible:
        return tuple(base[:3])
    if explored:
        return dim(base)
    return UNSEEN
