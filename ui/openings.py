"""P39.5 — stair, window & door variants (procedural, thin pygame draw).

Different themes read differently (from the building-gen research): a keep has a
SPIRAL stair, a crypt cold STONE steps, a home WOODEN ones; a temple has LANCET
windows, a cathedral a ROSE window, a castle ARROW-LOOPS, a cottage plain panes.
Pure geometry, cached where it pays; `sprite_loader`/`renderer_buildings` call in.
"""

import math

import pygame

_CACHE = {}

STONE = (128, 124, 116)
STONE_DK = (86, 82, 76)
STONE_LT = (168, 164, 156)
WOOD = (146, 108, 66)
WOOD_DK = (104, 74, 44)
IRON = (70, 72, 80)
GLASS = (120, 150, 170)
FRAME = (54, 46, 40)

# ---- STAIRS ---------------------------------------------------------------

STAIR_KINDS = ("wood", "stone", "spiral")


def _steps(surf, ts, base, dark, lt):
    n = 5
    for i in range(n):
        y = 4 + i * ((ts - 8) // n)
        x = 4 + i * 2
        w = ts - 8 - i * 4
        pygame.draw.rect(surf, base, (x, y, w, (ts - 8) // n))
        pygame.draw.line(surf, dark, (x, y), (x + w, y), 1)
        pygame.draw.line(surf, lt, (x, y + 1), (x + w, y + 1), 1)


def _spiral(surf, ts):
    cx, cy = ts // 2, ts // 2
    R = ts // 2 - 3
    for r in range(R, 3, -2):                    # concentric treads
        shade = STONE if (r // 2) % 2 else STONE_DK
        pygame.draw.circle(surf, shade, (cx, cy), r, 2)
    for a in range(0, 360, 45):                  # radial step dividers
        ang = math.radians(a)
        pygame.draw.line(surf, STONE_DK, (cx, cy),
                         (cx + int(R * math.cos(ang)),
                          cy + int(R * math.sin(ang))), 1)
    pygame.draw.circle(surf, STONE_LT, (cx, cy), max(2, ts // 10))  # newel


def draw_stairs(ts: int, kind: str = "wood") -> pygame.Surface:
    """A cached tile-sized staircase sprite for the given theme kind."""
    key = ("stair", kind, ts)
    if key not in _CACHE:
        s = pygame.Surface((ts, ts), pygame.SRCALPHA)
        if kind == "spiral":
            _spiral(s, ts)
        elif kind == "stone":
            _steps(s, ts, STONE, STONE_DK, STONE_LT)
        else:
            _steps(s, ts, WOOD, WOOD_DK, (176, 138, 92))
        _CACHE[key] = s
    return _CACHE[key]


def stair_kind_for(theme: dict) -> str:
    return (theme or {}).get("stair", "wood")


# ---- WINDOWS --------------------------------------------------------------

_WINDOW_BY_KIND = {
    "temple": "lancet", "library": "arched", "hall": "arched",
    "wall_tower": "arrow_loop", "watchtower": "arrow_loop",
    "tower": "arrow_loop", "keep": "arrow_loop",
    "tavern": "square", "inn": "square", "mill": "square",
}


def window_shape_for(kind: str) -> str:
    return _WINDOW_BY_KIND.get(kind, "square")


def draw_window(target, rect, shape: str,
                frame=FRAME, glass=GLASS) -> None:
    """Draw a window of `shape` at rect (x, y, w, h) on a wall face."""
    x, y, w, h = rect
    w = max(2, w)
    h = max(2, h)
    if shape == "arrow_loop":
        sw = max(2, w // 3)
        sx = x + (w - sw) // 2
        pygame.draw.rect(target, (20, 20, 24), (sx, y - h // 2, sw, h + h // 2))
        pygame.draw.rect(target, IRON, (x, y + h // 3, w, max(1, h // 4)))
        return
    if shape == "round" or shape == "rose":
        cx, cy, r = x + w // 2, y + h // 2, max(2, min(w, h) // 2)
        pygame.draw.circle(target, frame, (cx, cy), r + 1)
        pygame.draw.circle(target, glass, (cx, cy), r)
        if shape == "rose":
            for a in range(0, 360, 60):
                ang = math.radians(a)
                pygame.draw.line(target, frame, (cx, cy),
                                 (cx + int(r * math.cos(ang)),
                                  cy + int(r * math.sin(ang))), 1)
        return
    if shape == "lancet":                        # tall pointed gothic light
        top = y - h // 2
        pygame.draw.rect(target, frame, (x, y - h // 4, w, h + h // 4))
        pygame.draw.rect(target, glass, (x + 1, y, max(1, w - 2), h - 1))
        pygame.draw.polygon(target, glass, [(x, y), (x + w, y),
                                            (x + w // 2, top)])
        pygame.draw.polygon(target, frame, [(x, y), (x + w, y),
                                            (x + w // 2, top)], 1)
        return
    if shape == "arched":                        # rounded top
        pygame.draw.rect(target, frame, (x, y, w, h))
        pygame.draw.rect(target, glass, (x, y + h // 3, w, h - h // 3))
        pygame.draw.circle(target, glass, (x + w // 2, y + h // 3), w // 2)
        pygame.draw.circle(target, frame, (x + w // 2, y + h // 3), w // 2, 1)
        return
    # square (the default)
    pygame.draw.rect(target, frame, (x, y, w, h))
    pygame.draw.rect(target, glass, (x, y, w, max(1, h - 1)))
    if w >= 6:                                    # a mullion
        pygame.draw.line(target, frame, (x + w // 2, y),
                         (x + w // 2, y + h), 1)
