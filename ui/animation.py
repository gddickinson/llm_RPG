"""Animation math (P15.2) — pure, headless, testable.

Track G's animation work is mostly pixels, but the DECISIONS behind the
pixels are math: which of two frames a shimmering tile shows this
instant, how dark the sky is at 18:47, what colour a surface pulses to.
Pull that math out of the renderer (where it can't be unit-tested and
crowds the 500-line ceiling) into pure functions here — the same move
`battle_camera.py` made for the battle screen. The renderer and the
lighting overlay call these; the tests pin them to exact values.

Wired consumers so far:
  * `ambient_darkness(hour)` — `ui/lighting.py`, the night overlay: a
    smooth per-minute dusk->night->dawn ramp replacing a 4-step snap.
  * `surface_fill(kind, clock)` — `ui/renderer.py`, the P10.3 surface
    overlays: fire flickers, electrified water crackles, water shimmers
    (two-frame animation via `frame_index`), oil/blood sit still.

The remaining primitives (`lerp`/`smoothstep`/`lerp_color`) are the
shared vocabulary the later P15.2/P15.3/P15.4 rounds (walk-bob easing,
eased camera, colour lights) will draw on.
"""

from typing import Sequence, Tuple

Color = Tuple[int, ...]


# ---- interpolation vocabulary ---------------------------------------

def clamp(v: float, lo: float, hi: float) -> float:
    return lo if v < lo else hi if v > hi else v


def lerp(a: float, b: float, t: float) -> float:
    """Linear blend a->b as t goes 0->1 (t is NOT clamped)."""
    return a + (b - a) * t


def smoothstep(t: float) -> float:
    """Ease-in-out on [0,1]: flat at both ends, steep in the middle."""
    t = clamp(t, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def lerp_color(c1: Sequence[int], c2: Sequence[int], t: float) -> Color:
    """Per-channel blend of two RGB(A) colours; result rounded to ints."""
    t = clamp(t, 0.0, 1.0)
    return tuple(int(round(lerp(a, b, t))) for a, b in zip(c1, c2))


# ---- two-frame animation clock --------------------------------------

# seconds each frame of a two-frame loop is held (0 = not animated)
_SEC_PER_FRAME = {"fire": 0.12, "electrified": 0.07, "water": 0.9}


def frame_index(clock: float, kind: str) -> int:
    """Which frame (0 or 1) an animated `kind` shows at time `clock`
    (seconds). Static kinds never leave frame 0."""
    spf = _SEC_PER_FRAME.get(kind, 0.0)
    if spf <= 0.0 or clock < 0.0:
        return 0
    return int(clock / spf) % 2


# ---- P10.3 surface overlay colours (data + flicker) -----------------

def surface_fill(kind: str, clock: float = 0.0) -> Color:
    """The RGBA an overlaid surface tile should fill this instant.

    Fire and electrified water alternate between a dim and a bright
    frame (flicker / crackle); water breathes a gentle shimmer; oil and
    blood are inert. Moving this out of the renderer both animates the
    surfaces and turns their palette into tested data.
    """
    f = frame_index(clock, kind)
    if kind == "fire":
        return (250, 120, 20, 150 + 40 * f)
    if kind == "electrified":
        return (150, 220, 255, 160 + 60 * f)
    if kind == "water":
        return (60, 120, 220, 90 + 18 * f)
    if kind == "oil":
        return (40, 35, 30, 120)
    if kind == "blood":
        return (140, 20, 25, 110)
    return (60, 120, 220, 90)            # unknown -> water-like default


# ---- eased day/night darkness ---------------------------------------

# (hour, darkness-alpha) keyframes over a 24h day; between them the ramp
# is smoothstepped, so the sky darkens minute-by-minute instead of
# snapping at the boundaries of morning/evening/night. Anchored to the
# old discrete table: full day 0, evening ~80 near 18:30, night ~170.
_DARK_KEYS = [
    (0.0, 170), (4.5, 170), (7.0, 0), (16.5, 0),
    (19.5, 100), (21.5, 170), (24.0, 170),
]


def ambient_darkness(hour: float) -> int:
    """Ambient night-overlay alpha (0=bright day .. ~170=deep night) for
    a continuous hour-of-day, eased between keyframes."""
    h = hour % 24.0
    for (h0, d0), (h1, d1) in zip(_DARK_KEYS, _DARK_KEYS[1:]):
        if h0 <= h <= h1:
            span = h1 - h0
            t = 0.0 if span <= 0 else (h - h0) / span
            return int(round(lerp(d0, d1, smoothstep(t))))
    return 0
