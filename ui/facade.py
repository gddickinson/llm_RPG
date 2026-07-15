"""BLD.4 — building FACADE detail: real entrance doors (BLD.5 adds shopfronts).

The old door was a flat coloured rect (`door_glyphs`), the same for every
building. Here a door is chosen by building KIND and drawn with a frame, a
lintel above and a step below: a PANELLED door for homes/shops, a PLANKED,
stud-and-brace door for a smithy/barn, an ARCHED door for a temple/library, a
DOUBLE door for a hall/inn/keep. The lock-state COLOUR (open/closed/locked/
broken) is preserved. Pure geometry (`door_shapes`) + a thin pygame draw
(`draw_door`), headless-testable, in the `roof_shapes.py` mould.
"""

_PLANKED = {"smithy", "forge", "barn", "stable", "storeroom", "warehouse",
            "granary", "mill", "sawmill", "lodge", "farmhouse", "dock", "stall"}
_ARCHED = {"temple", "chapel", "shrine", "library", "tower"}
_DOUBLE = {"hall", "inn", "keep", "castle"}


def door_style_for(kind: str) -> str:
    """The door style a building kind shows — the visual cue to what it is."""
    k = (kind or "").lower()
    if k in _PLANKED:
        return "planked"
    if k in _ARCHED:
        return "arched"
    if k in _DOUBLE:
        return "double"
    return "panelled"


def door_box(sx: int, sy: int, ts: int):
    """The (x, y, w, h) of the door leaf on a tile's south face."""
    w = max(8, int(ts * 0.44))
    h = max(12, int(ts * 0.64))
    return (sx + (ts - w) // 2, sy + ts - h, w, h)


def door_shapes(x: int, y: int, w: int, h: int, style: str) -> dict:
    """Pure geometry for a door of `style` in the box (x, y, w, h): the frame,
    lintel, step, leaf(s), and the style detail (panels / planks+studs+brace /
    arch / double leaves). Consumed by `draw_door`; asserted by the tests."""
    s = {"lintel": (x - 1, y - max(2, h // 10), w + 2, max(2, h // 10)),
         "step": (x - 1, y + h, w + 2, max(2, h // 12)),
         "jambs": [(x - 1, y, 1, h), (x + w, y, 1, h)],
         "leaf": (x, y, w, h), "style": style}
    if style == "panelled":
        pw, ph = max(2, w // 2 - 2), max(2, h // 2 - 3)
        s["panels"] = [(x + 2, y + 2, pw, ph),
                       (x + w - pw - 2, y + 2, pw, ph),
                       (x + 2, y + h - ph - 2, pw, ph),
                       (x + w - pw - 2, y + h - ph - 2, pw, ph)]
        s["knob"] = (x + w - 3, y + h // 2)
    elif style == "planked":
        n = max(2, w // 4)
        s["planks"] = [x + (i + 1) * w // (n + 1) for i in range(n)]
        s["studs"] = [(x + 2, y + 2), (x + w - 3, y + 2),
                      (x + 2, y + h - 3), (x + w - 3, y + h - 3)]
        s["brace"] = ((x + 1, y + h - 1), (x + w - 1, y + 1))   # diagonal
    elif style == "arched":
        s["arch_r"] = w // 2                       # rounded top radius
        s["knob"] = (x + w - 3, y + h // 2)
    elif style == "double":
        half = w // 2
        s["leaves"] = [(x, y, half, h), (x + half, y, w - half, h)]
        s["meeting"] = (x + half, y, 1, h)
        s["arch_r"] = w // 2
    return s


def _scale(c, f):
    return tuple(max(0, min(255, int(v * f))) for v in c[:3])


def draw_door(target, sx: int, sy: int, ts: int, kind: str, state: str) -> None:
    """Draw a per-kind entrance door on a tile's south face, coloured by lock
    state. Thin pygame over `door_shapes`."""
    import pygame
    from ui.door_glyphs import DOOR_STATE_COLORS
    style = door_style_for(kind)
    x, y, w, h = door_box(sx, sy, ts)
    s = door_shapes(x, y, w, h, style)
    col = DOOR_STATE_COLORS.get(state, (110, 75, 40))
    dark, light = _scale(col, 0.55), _scale(col, 1.28)
    stone, iron = (92, 84, 76), (40, 34, 28)

    pygame.draw.rect(target, _scale(stone, 1.05), s["step"])       # threshold
    r = s.get("arch_r", 0)
    # leaf(s)
    if style == "double":
        for lx, ly, lw, lh in s["leaves"]:
            pygame.draw.rect(target, col, (lx, ly, lw, lh),
                             border_top_left_radius=r, border_top_right_radius=r)
            pygame.draw.rect(target, dark, (lx, ly, lw, lh), 1,
                             border_top_left_radius=r, border_top_right_radius=r)
        pygame.draw.rect(target, iron, s["meeting"])
    else:
        pygame.draw.rect(target, col, (x, y, w, h),
                         border_top_left_radius=r, border_top_right_radius=r)
        pygame.draw.rect(target, dark, (x, y, w, h), 1,
                         border_top_left_radius=r, border_top_right_radius=r)
    # frame: jambs + lintel
    for jx, jy, jw, jh in s["jambs"]:
        pygame.draw.rect(target, stone, (jx, jy, jw, jh))
    pygame.draw.rect(target, _scale(stone, 1.15), s["lintel"])
    # style detail
    if style == "panelled":
        for p in s["panels"]:
            pygame.draw.rect(target, dark, p, 1)
        pygame.draw.circle(target, (210, 190, 90), s["knob"], 1)
    elif style == "planked":
        for px in s["planks"]:
            pygame.draw.line(target, dark, (px, y + 1), (px, y + h - 1), 1)
        pygame.draw.line(target, light, s["brace"][0], s["brace"][1], 1)
        for (dxp, dyp) in s["studs"]:
            pygame.draw.circle(target, iron, (dxp, dyp), 1)
    elif style in ("arched", "double"):
        pygame.draw.circle(target, (210, 190, 90), s.get(
            "knob", (x + w - 3, y + h // 2)), 1)
    # lock state
    if state == "locked":
        pygame.draw.circle(target, (220, 205, 95),
                           (x + w // 2, y + h * 2 // 3), 2)
    elif state == "open":
        pygame.draw.rect(target, (14, 11, 8), (x + 2, y + 3, w - 4, h - 4),
                         border_top_left_radius=r, border_top_right_radius=r)
    elif state == "broken":
        pygame.draw.line(target, iron, (x, y), (x + w, y + h), 2)
