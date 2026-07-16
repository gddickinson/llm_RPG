"""ISO.15 — footprint-spanning BUILDING boxes for the isometric world.

A building had been drawn as ONE fixed baked sprite parked at its front tile, so
it never matched a footprint bigger than ~1 tile (George: "the buildings don't
match their footprints"). This draws each enterable building as a real 3D BOX
projected through the SAME iso projection as the ground tiles — two visible walls
(with a door + windows) rising from the whole `loc.width × loc.height` footprint
to a real ROOF (gable ridge / hip pyramid / flat parapet), in the building's own
style materials. Because it uses `iso.world_to_screen`, the box lands exactly on
its footprint. Pure projection + polygon fills; `iso_render` calls in.
"""

from ui import roof_shapes as rs
from ui.renderer_buildings import storeys_for, style_for

_STOREY_Z = 0.62                      # building height per storey, in z-units
_WIN = (46, 44, 56)
_DOOR = (58, 40, 28)


def _scale(c, f):
    return (max(0, min(255, int(c[0] * f))), max(0, min(255, int(c[1] * f))),
            max(0, min(255, int(c[2] * f))))


def building_infos(engine):
    """[(x0, y0, x1, y1, kind)] for each enterable building (its footprint)."""
    out = []
    try:
        from world.blueprints import blueprint_for_location
    except Exception:
        blueprint_for_location = None
    ints = getattr(engine, "interiors", {}) or {}
    for loc in getattr(engine.world, "locations", []):
        if loc.name not in ints:
            continue
        kind = "home"
        if blueprint_for_location is not None:
            bp = blueprint_for_location(loc.name)
            kind = (getattr(bp, "kind", "") or "home") if bp else "home"
        w, h = max(1, loc.width), max(1, loc.height)
        out.append((loc.x, loc.y, loc.x + w - 1, loc.y + h - 1, kind))
    return out


def footprint_tiles(engine):
    """The set of tiles covered by an enterable building — drawn as GROUND (no
    lifted brown pedestal) so the spanning box sits on flat earth."""
    tiles = set()
    for x0, y0, x1, y1, _ in building_infos(engine):
        for wx in range(x0, x1 + 1):
            for wy in range(y0, y1 + 1):
                tiles.add((wx, wy))
    return tiles


def _poly(target, pygame, col, pts):
    pygame.draw.polygon(target, col, [(int(a), int(b)) for a, b in pts])


def draw_building(target, iso, origin, info, cov, wall):
    """Project the footprint box + roof and draw the visible faces."""
    import pygame
    x0, y0, x1, y1, kind = info
    style = style_for(kind)
    wall_c = rs.wall_color(wall or style.get("wall", "timber"))
    cover_c = rs.covering_color(cov or style.get("covering", "clay"))
    storeys = max(1, storeys_for(kind))
    H = storeys * _STOREY_Z

    def P(wx, wy, z):
        return iso.world_to_screen(wx, wy, z, origin)

    # outer footprint corners: N(back) E(right) S(front) W(left)
    xa, xb, ya, yb = x0 - 0.5, x1 + 0.5, y0 - 0.5, y1 + 0.5
    N0, E0, S0, W0 = P(xa, ya, 0), P(xb, ya, 0), P(xb, yb, 0), P(xa, yb, 0)
    N1, E1, S1, W1 = P(xa, ya, H), P(xb, ya, H), P(xb, yb, H), P(xa, yb, H)

    # the two camera-facing walls (share the front S corner)
    _poly(target, pygame, _scale(wall_c, 0.62), [W0, S0, S1, W1])   # south (dark)
    _poly(target, pygame, _scale(wall_c, 0.82), [E0, S0, S1, E1])   # east (mid)
    _windows(target, pygame, P, xa, xb, ya, yb, storeys)
    _door(target, pygame, P, x0, x1, yb)

    shape = style.get("roof", "gable")
    tall = kind in ("tower", "keep", "watchtower", "wall_tower", "mill")
    if shape == "flat" or tall:
        _poly(target, pygame, cover_c, [N1, E1, S1, W1])           # flat top
        top = _scale(cover_c, 1.06)
        cap = [P(xa, ya, H + 0.12), P(xb, ya, H + 0.12),
               P(xb, yb, H + 0.12), P(xa, yb, H + 0.12)]
        _poly(target, pygame, _scale(cover_c, 0.7), [W1, S1, cap[2], cap[3]])
        _poly(target, pygame, _scale(cover_c, 0.85), [E1, S1, cap[2], cap[1]])
        _poly(target, pygame, top, cap)
    elif shape == "hip" or (x1 - x0) == (y1 - y0):
        apex = P((xa + xb) / 2, (ya + yb) / 2, H + 0.5 + 0.14 * storeys)
        _poly(target, pygame, _scale(cover_c, 0.78), [W1, S1, apex])
        _poly(target, pygame, _scale(cover_c, 0.95), [E1, S1, apex])
        _poly(target, pygame, _scale(cover_c, 0.68), [N1, W1, apex])
    else:                                                          # gable ridge
        rh = 0.5 + 0.12 * storeys
        if (x1 - x0) >= (y1 - y0):                    # ridge runs east–west (x)
            cy = (ya + yb) / 2
            rW, rE = P(xa, cy, H + rh), P(xb, cy, H + rh)
            _poly(target, pygame, _scale(cover_c, 0.95), [W1, S1, rE, rW])
            _poly(target, pygame, _scale(cover_c, 0.7), [E1, S1, rE])
        else:                                         # ridge runs north–south
            cx = (xa + xb) / 2
            rN, rS = P(cx, ya, H + rh), P(cx, yb, H + rh)
            _poly(target, pygame, _scale(cover_c, 0.82), [E1, S1, rS, rN])
            _poly(target, pygame, _scale(cover_c, 0.95), [W1, S1, rS])


def _windows(target, pygame, P, xa, xb, ya, yb, storeys):
    """A pair of dark windows per storey on the south + east walls."""
    span_x = xb - xa
    span_y = yb - ya
    for s in range(storeys):
        zc = s * _STOREY_Z + _STOREY_Z * 0.42
        zt = zc + _STOREY_Z * 0.34
        for f in (0.32, 0.68):                       # south wall (front, y=yb)
            wx = xa + span_x * f
            _poly(target, pygame, _WIN,
                  [P(wx - span_x * 0.09, yb, zc), P(wx + span_x * 0.09, yb, zc),
                   P(wx + span_x * 0.09, yb, zt), P(wx - span_x * 0.09, yb, zt)])
        for f in (0.32, 0.68):                       # east wall (right, x=xb)
            wy = ya + span_y * f
            _poly(target, pygame, _scale(_WIN, 0.85),
                  [P(xb, wy - span_y * 0.09, zc), P(xb, wy + span_y * 0.09, zc),
                   P(xb, wy + span_y * 0.09, zt), P(xb, wy - span_y * 0.09, zt)])


def _door(target, pygame, P, x0, x1, yb):
    """A door centred on the south (front) wall."""
    cx = (x0 + x1) / 2 + 0.5
    _poly(target, pygame, _DOOR,
          [P(cx - 0.34, yb, 0), P(cx + 0.34, yb, 0),
           P(cx + 0.34, yb, _STOREY_Z * 0.78), P(cx - 0.34, yb, _STOREY_Z * 0.78)])
