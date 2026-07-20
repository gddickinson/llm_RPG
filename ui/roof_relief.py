"""BLD.8 — roof relief, depth & weathering (pure geometry + thin pygame draw).

The roof is where a 2.5D building reads flat or solid. This adds the depth cues
and age that make it read as a real roof:

- an EAVES overhang: a soffit-shadow band where the roof projects over the wall
  top, so the roof visibly sits ON the wall rather than being painted flush;
- a RIDGE CAP: a highlighted capping course along the ridge line;
- DORMERS: a small gabled roof-window on a grand building's front slope;
- deterministic WEATHERING: moss patches + dark rain-streak stains scattered by
  the building's WORLD position, so two buildings of the same kind never look
  identical (George: "so clones differ").

Everything is seeded off the building's world (wx, wy) via a pure integer hash
(no RNG object, no per-frame flicker — the same building weathers the same way
every frame). Thin `draw_*` helpers the 2.5D building renderer calls; the roof
geometry itself still comes from `roof_shapes.py`.
"""

import pygame

MOSS = (74, 92, 54)
MOSS_DK = (58, 74, 42)
STAIN = (52, 46, 40)


def _scale(c, f):
    return tuple(max(0, min(255, int(v * f))) for v in c[:3])


def _hash(a: int, b: int, salt: int) -> int:
    h = (int(a) * 73856093) ^ (int(b) * 19349663) ^ (salt * 83492791)
    return h & 0x7FFFFFFF


# ---- eaves / soffit ------------------------------------------------------

def soffit_rect(sx: int, eave_y: int, width: int, ts: int):
    """The shadow band under the roof overhang, along the wall top."""
    bh = max(1, ts // 9)
    return (sx, eave_y, width, bh)


def draw_eaves(target, sx: int, eave_y: int, width: int, ts: int,
               front_color) -> None:
    """A soffit-shadow band + a lit overhang lip, so the roof overhangs."""
    if ts < 12:
        return
    br = soffit_rect(sx, eave_y, width, ts)
    band = pygame.Surface((br[2], br[3]), pygame.SRCALPHA)
    band.fill((0, 0, 0, 90))
    target.blit(band, (br[0], br[1]))
    # a thin lit lip at the very eave line (the projecting edge catches light)
    pygame.draw.line(target, _scale(front_color, 1.5),
                     (sx, eave_y), (sx + width, eave_y), 1)


# ---- ridge cap -----------------------------------------------------------

def draw_ridge_cap(target, p1, p2, shades, ts: int) -> None:
    """A capping course sitting proud on the ridge — a bright cap over a
    slightly wider shadow, so the ridge reads as a raised ridge tile."""
    if not p1 or not p2:
        return
    w = max(1, ts // 12)
    pygame.draw.line(target, shades["shadow"], p1, p2, w + 2)
    pygame.draw.line(target, shades["ridge"], p1, p2, max(1, w))


# ---- weathering (deterministic per world position) -----------------------

def weathering_spots(wx: int, wy: int, x0: int, y0: int, w: int, h: int,
                     n: int = 5):
    """`n` moss/stain blobs (x, y, r, is_moss) over a roof rect — deterministic
    from the building's world position so clones weather differently."""
    if w < 6 or h < 4:
        return []
    out = []
    for i in range(n):
        hx = _hash(wx, wy, i * 2 + 1)
        hy = _hash(wx, wy, i * 2 + 2)
        px = x0 + (hx % max(1, w))
        py = y0 + (hy % max(1, h))
        r = 1 + (hx % 3)
        is_moss = (hy % 5) < 2                       # ~40% moss, else a stain
        out.append((px, py, r, is_moss))
    return out


def draw_weathering(target, spots, clip_rect) -> None:
    """Moss (soft green) + rain-stain (dark) blobs, clipped to the roof."""
    if not spots:
        return
    prev = target.get_clip()
    target.set_clip(clip_rect)
    try:
        for (px, py, r, is_moss) in spots:
            if is_moss:
                pygame.draw.circle(target, MOSS, (px, py), r)
                pygame.draw.circle(target, MOSS_DK, (px, py), max(1, r - 1))
            else:                                    # a stain streaks downslope
                pygame.draw.line(target, STAIN, (px, py), (px, py + r * 2),
                                 max(1, r - 1))
    finally:
        target.set_clip(prev)


# ---- dormers -------------------------------------------------------------

def dormer_boxes(sx: int, roof_top: int, eave_y: int, width: int, ts: int):
    """1-2 small dormer (x, y, w, h) faces on the front (lower) roof slope of a
    wide enough roof. Empty when the roof is too small to carry one."""
    if width < ts * 2 or eave_y - roof_top < ts // 2 or ts < 20:
        return []
    dw = max(4, ts // 3)
    dh = max(3, ts // 4)
    slope = roof_top + (eave_y - roof_top) * 2 // 3   # sit low on the slope
    dy = slope - dh
    n = 2 if width >= ts * 3 else 1
    out = []
    for i in range(n):
        dx = sx + width * (i + 1) // (n + 1) - dw // 2
        out.append((dx, dy, dw, dh))
    return out


def draw_dormers(target, boxes, shades, ts: int) -> None:
    """A small gabled dormer with a dark window on each box."""
    glass = (44, 40, 52)
    for (dx, dy, dw, dh) in boxes:
        pygame.draw.rect(target, shades["mid"], (dx, dy, dw, dh))
        # a little gable cap
        pygame.draw.polygon(target, shades["lit"],
                            [(dx - 1, dy), (dx + dw + 1, dy),
                             (dx + dw // 2, dy - max(2, dh // 2))])
        # the dormer window
        iw, ih = max(2, dw - 3), max(2, dh - 2)
        pygame.draw.rect(target, glass,
                         (dx + (dw - iw) // 2, dy + dh - ih - 1, iw, ih))
