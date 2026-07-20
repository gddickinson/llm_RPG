"""BLD.7 — architectural facade TRIM (pure geometry + thin pygame draw).

The fine detail that makes a 2.5D building front read as *built* rather than a
blank painted box: SHUTTERS flanking each window, a stone SILL under it (and a
LINTEL over it on grander buildings), QUOINS (dressed corner stones stepping up
the front corners) and a CORNICE band riding under the roof eave.

Pure `(x, y, w, h)` rect geometry in the `roof_shapes.py` / `gate_shapes.py` /
`openings.py` mould — headless-testable — plus thin `draw_*` helpers the 2.5D
building renderer calls. `trim_style_for(kind)` decides which trim a building
shows: a grand temple/hall/keep gets the full dress (quoins + cornice + lintel),
a plain home just shutters + a sill. The front wall is the axis-aligned rect
from the eave (`sy + ts - h`) down to the ground (`sy + ts`); trim geometry is
derived from that, so it lines up with `renderer_buildings.cube_faces`.
"""

import pygame

# palette — dressed stone trim + painted timber shutters
STONE = (156, 148, 134)
STONE_DK = (112, 105, 92)
SHUTTER = (98, 70, 46)
SHUTTER_DK = (68, 48, 30)

# buildings that carry the FULL architectural dress (quoins/cornice/lintel)
_GRAND = {"temple", "cathedral", "church", "chapel", "shrine", "hall", "keep",
          "castle", "library", "inn", "tavern", "tower", "wall_tower",
          "guildhall", "manor"}


def trim_style_for(kind: str) -> dict:
    """Which trim a building kind shows — grand civic/sacred buildings get the
    full stone dress; a plain home just shutters + a sill."""
    grand = (kind or "").lower() in _GRAND
    return {"shutters": True, "sill": True,
            "lintel": grand, "quoins": grand, "cornice": grand}


# ---- window trim geometry -----------------------------------------------

def shutter_rects(x: int, y: int, w: int, h: int):
    """The two timber shutters flanking a window rect (x, y, w, h)."""
    sw = max(1, (w * 2) // 3)
    return [(x - sw - 1, y, sw, h), (x + w + 1, y, sw, h)]


def sill_rect(x: int, y: int, w: int, h: int):
    """The stone sill ledge under a window."""
    sh = max(1, h // 4)
    return (x - 1, y + h, w + 2, sh)


def lintel_rect(x: int, y: int, w: int, h: int):
    """The stone lintel bar over a window."""
    lh = max(1, h // 4)
    return (x - 1, y - lh, w + 2, lh)


# ---- corner / eave trim geometry ----------------------------------------

def cornice_rect(sx: int, sy: int, ts: int, h: int):
    """A projecting band riding the wall-top under the roof, or None."""
    if ts < 16 or h < 6:
        return None
    eave = sy + ts - h
    ch = max(1, ts // 12)
    return (sx, eave, ts, ch)


def quoin_blocks(sx: int, sy: int, ts: int, h: int):
    """Dressed corner stones stepping up BOTH front corners (a quoin chain),
    laid every other course so they alternate. Empty on a small block."""
    if ts < 20 or h < 8:
        return []
    qw = max(2, ts // 8)
    qh = max(2, ts // 8)
    eave = sy + ts - h
    ground = sy + ts
    span = ground - eave
    n = max(2, span // (qh + 1))
    out = []
    for i in range(n):
        if i % 2:                          # every other course
            continue
        by = eave + i * span // n
        out.append((sx, by, qw, qh))                 # left corner
        out.append((sx + ts - qw, by, qw, qh))       # right corner
    return out


# ---- thin draws ---------------------------------------------------------

def draw_window_trim(target, rect, style: dict, ts: int) -> None:
    """Sill / lintel / shutters around a window. Drawn BEFORE the window so the
    glazing sits crisply on top. Skipped when the tile is too small to read."""
    if ts < 18:
        return
    x, y, w, h = rect
    if style.get("sill"):
        pygame.draw.rect(target, STONE, sill_rect(x, y, w, h))
    if style.get("lintel"):
        pygame.draw.rect(target, STONE, lintel_rect(x, y, w, h))
    if style.get("shutters") and w >= 3:
        for r in shutter_rects(x, y, w, h):
            if r[2] < 1:
                continue
            pygame.draw.rect(target, SHUTTER, r)
            pygame.draw.rect(target, SHUTTER_DK, r, 1)


def draw_corner_trim(target, sx: int, sy: int, ts: int, h: int,
                     style: dict) -> None:
    """Cornice band + corner quoins on a building block front."""
    if ts < 16:
        return
    if style.get("cornice"):
        c = cornice_rect(sx, sy, ts, h)
        if c is not None:
            pygame.draw.rect(target, STONE, c)
            pygame.draw.rect(target, STONE_DK, c, 1)
    if style.get("quoins"):
        for r in quoin_blocks(sx, sy, ts, h):
            pygame.draw.rect(target, STONE, r)
            pygame.draw.rect(target, STONE_DK, r, 1)


def span_quoin_blocks(px: int, fy: int, ground: int, w: int, ts: int):
    """Quoins up the two OUTER corners of a footprint-spanning front."""
    if ts < 20 or ground - fy < 8:
        return []
    qw = max(2, ts // 8)
    qh = max(2, ts // 8)
    span = ground - fy
    n = max(2, span // (qh + 1))
    out = []
    for i in range(n):
        if i % 2:
            continue
        by = fy + i * span // n
        out.append((px, by, qw, qh))                 # left outer corner
        out.append((px + w - qw, by, qw, qh))        # right outer corner
    return out


def draw_span_corner_trim(target, px: int, fy: int, ground: int, w: int,
                          ts: int, style: dict) -> None:
    """Cornice band across the full footprint width + outer-corner quoins."""
    if ts < 16:
        return
    if style.get("cornice"):
        ch = max(1, ts // 12)
        pygame.draw.rect(target, STONE, (px, fy, w, ch))
        pygame.draw.rect(target, STONE_DK, (px, fy, w, ch), 1)
    if style.get("quoins"):
        for r in span_quoin_blocks(px, fy, ground, w, ts):
            pygame.draw.rect(target, STONE, r)
            pygame.draw.rect(target, STONE_DK, r, 1)
