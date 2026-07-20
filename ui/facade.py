"""BLD.4/5 — building FACADE detail: entrance DOORS (BLD.4) + SHOPFRONTS (BLD.5).

BLD.4: a door chosen by building KIND — a PANELLED door for homes/shops, a
PLANKED stud-and-brace door for a smithy/barn, an ARCHED door for a temple/
library, a DOUBLE door for a hall/inn/keep — framed with a lintel + step, the
lock-state COLOUR preserved.

BLD.5: a shopfront so a business reads from the STREET — a striped AWNING + a
projecting HANGING SIGN with a trade emblem (a mug=tavern, loaf=bakery,
coin=shop), a DISPLAY window for a shop, a forge-GLOW + anvil for a smithy, an
oven-glow for a bakery. `shopfront_for(kind)` names the motifs; `draw_shopfront`
lays them over the south face (before the door). Pure geometry + thin pygame,
headless-testable, in the `roof_shapes.py` mould.
"""

_PLANKED = {"smithy", "forge", "barn", "stable", "storeroom", "warehouse",
            "granary", "mill", "sawmill", "lodge", "farmhouse", "dock", "stall"}
_ARCHED = {"temple", "chapel", "shrine", "library", "tower",
           "cathedral", "church"}
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


# ---- BLD.5 shopfronts & signage ------------------------------------------

# per-kind street identity: awning colour, hanging-sign trade emblem, and
# whether the front shows a display window / forge glow / oven glow
_SHOPFRONTS = {
    "tavern": {"awning": (150, 60, 55), "sign": "mug"},
    "alehouse": {"awning": (150, 60, 55), "sign": "mug"},
    "inn": {"awning": (92, 72, 140), "sign": "mug"},
    "shop": {"awning": (70, 112, 92), "sign": "coin", "display": True},
    "stall": {"awning": (172, 142, 72), "sign": "coin", "display": True},
    "market": {"awning": (172, 142, 72), "sign": "coin", "display": True},
    "bakery": {"awning": (204, 154, 92), "sign": "loaf", "oven": True},
    "smithy": {"sign": "anvil", "forge": True},
    "forge": {"sign": "anvil", "forge": True},
}


def shopfront_for(kind: str) -> dict:
    """The street-facing motifs a building kind shows (empty for a plain home)."""
    return _SHOPFRONTS.get((kind or "").lower(), {})


def _glow(target, cx, cy, r, color):
    import pygame
    for i in range(r, 0, -2):
        a = max(8, int(90 * (1 - i / r)))
        s = pygame.Surface((i * 2, i * 2), pygame.SRCALPHA)
        pygame.draw.circle(s, (*color, a), (i, i), i)
        target.blit(s, (cx - i, cy - i))


def _emblem(target, cx, cy, r, trade):
    import pygame
    gold, dark = (222, 200, 110), (60, 45, 25)
    if trade == "mug":
        pygame.draw.rect(target, gold, (cx - r, cy - r, 2 * r - 1, 2 * r))
        pygame.draw.arc(target, gold, (cx + r - 2, cy - r, r, 2 * r),
                        -1.4, 1.4, 1)
    elif trade == "loaf":
        pygame.draw.ellipse(target, (206, 170, 110),
                            (cx - r, cy - r // 2, 2 * r, r + 1))
    elif trade == "anvil":
        pygame.draw.rect(target, (150, 150, 160), (cx - r, cy - 1, 2 * r, 2))
        pygame.draw.polygon(target, (150, 150, 160),
                            [(cx + r - 1, cy - 1), (cx + r + 1, cy - 3),
                             (cx + r + 1, cy - 1)])
        pygame.draw.rect(target, (110, 110, 120), (cx - 1, cy + 1, 2, r))
    else:                                    # coin / scales
        pygame.draw.circle(target, gold, (cx, cy), max(2, r - 1))
        pygame.draw.circle(target, dark, (cx, cy), max(2, r - 1), 1)


def draw_shopfront(target, sx: int, sy: int, ts: int, kind: str) -> None:
    """Draw a building's street identity on its south face, under/around the
    door: awning, hanging sign, display window, forge/oven glow."""
    import pygame
    spec = shopfront_for(kind)
    if not spec:
        return
    x, y, w, h = door_box(sx, sy, ts)
    # forge / oven glow — the warm open front
    if spec.get("forge") or spec.get("oven"):
        _glow(target, x + w // 2, y + h - 1, max(5, ts // 4),
              (255, 150, 60) if spec.get("forge") else (255, 180, 90))
    # display window — a glazed shopfront pane beside the door
    if spec.get("display"):
        dw = max(5, ts // 4)
        dx = x - dw - 1 if x - dw - 1 > sx else x + w + 1
        pygame.draw.rect(target, (54, 46, 40), (dx, y + 2, dw, h - 4))
        pygame.draw.rect(target, (150, 185, 200), (dx + 1, y + 3, dw - 2, h - 6))
        pygame.draw.line(target, (54, 46, 40), (dx + dw // 2, y + 3),
                         (dx + dw // 2, y + h - 3), 1)
    # awning — a striped canvas ledge above the door
    if "awning" in spec:
        col = spec["awning"]
        aw, ah = w + 4, max(3, ts // 9)
        ax, ay = x - 2, y - ah - 1
        stripe = max(2, aw // 5)
        for i in range(0, aw, stripe):
            c = col if (i // stripe) % 2 == 0 else (235, 228, 214)
            pygame.draw.rect(target, c, (ax + i, ay, min(stripe, aw - i), ah))
        pygame.draw.rect(target, _scale(col, 0.6), (ax, ay + ah - 1, aw, 1))
    # hanging sign — a small board on a bracket, to the upper-left, with emblem
    if "sign" in spec:
        bw, bh = max(7, ts // 5), max(6, ts // 6)
        bx = sx + max(1, ts // 12)
        by = sy + ts - h - bh - 1
        pygame.draw.line(target, (60, 45, 30), (bx, by), (bx + bw // 2, by), 1)
        pygame.draw.rect(target, (86, 64, 42), (bx, by + 1, bw, bh))
        pygame.draw.rect(target, (54, 40, 26), (bx, by + 1, bw, bh), 1)
        _emblem(target, bx + bw // 2, by + 1 + bh // 2, max(2, bh // 3),
                spec["sign"])
