"""Light & weather colour (P15.4) — pure, headless, testable.

The atmosphere layer, like the animation layer (P15.2) and the HUD
styling (P15.3), is mostly "given this source / this night, what
colour?" — so the decisions live here as pure functions the lighting
overlay calls, and the tests pin them exactly:

  * `light_color(kind)` — coloured light SOURCES: a forge burns orange,
    a marsh wisp glows blue-green, a torch is warm. The lighting overlay
    punches these hues so a wisp lights its bog differently than your
    torch lights the road.

  * `sky_tint(...)` — the whole-sky wash: a green AURORA on clear
    conjunction nights (the two moons together, P8.1), and a cool winter
    CHILL while it snows or on a deep winter night. Returns the RGBA the
    overlay blends over the darkened view (transparent when there's
    nothing to show).

Night depth reuses `animation.ambient_darkness`, so the atmosphere
fades in and out with the same eased day/night curve.
"""

from ui.animation import ambient_darkness

# coloured light sources (RGB)
LIGHT_COLORS = {
    "torch": (255, 200, 100),      # warm
    "window": (255, 220, 120),
    "forge": (255, 150, 40),       # orange
    "hearth": (255, 170, 70),
    "wisp": (120, 255, 200),       # blue-green
    "altar": (200, 180, 255),
    "magic": (180, 140, 255),
}
DEFAULT_LIGHT = (255, 220, 150)

# weather that isn't a clear sky (no aurora through cloud)
_OVERCAST = ("storm", "fog", "rain", "snow", "cloudy")

AURORA = (60, 210, 140)
WINTER_CHILL = (150, 180, 225)
CLEAR = (0, 0, 0, 0)


def light_color(kind: str) -> tuple:
    """The RGB a named light source glows."""
    return LIGHT_COLORS.get(kind, DEFAULT_LIGHT)


def night_factor(hour: float) -> float:
    """0 in full day .. 1 in deep night, on the eased curve."""
    return min(1.0, max(0.0, ambient_darkness(hour) / 170.0))


def sky_tint(hour: float, conjunction: bool = False,
             weather: str = "clear", season: str = "summer") -> tuple:
    """The RGBA wash the sky should get this moment: a green aurora on a
    clear conjunction night, a cool chill while it snows or on a deep
    winter night, else transparent."""
    n = night_factor(hour)
    clear = weather not in _OVERCAST
    # aurora — a green shimmer, clear conjunction nights only
    if conjunction and clear and n >= 0.5:
        return (*AURORA, int(20 + 35 * n))
    # winter chill — whenever it snows (day or night), or a winter night
    if weather == "snow":
        return (*WINTER_CHILL, int(25 + 25 * n))
    if season == "winter" and n >= 0.4:
        return (*WINTER_CHILL, int(20 * n))
    return CLEAR
