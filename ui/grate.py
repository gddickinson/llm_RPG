"""OAKVALE — a visible SEWER GRATE over a dungeon entrance (pure + thin draw).

George: "make the DeepDelve entrance more obvious — a visible grate/sewer
entrance." A `sewer_grate`-tagged `Location` (a CAVE tile that descends into the
Deepdelve) draws as a rusted IRON GRATE set in a stone kerb over a dark shaft —
so the way down reads at a glance instead of being a bare cave. Pure geometry
(`grate_geometry`) + a thin pygame draw (`draw_grate`); `draw_all` iterates the
in-view, explored grate Locations (called from `renderer_buildings`).
"""

import pygame

STONE = (124, 120, 112)
STONE_DK = (82, 78, 72)
SHAFT = (16, 14, 18)
IRON = (74, 74, 82)
IRON_HI = (120, 120, 132)
RUST = (110, 74, 48)


def grate_geometry(px: int, py: int, ts: int) -> dict:
    """The stone kerb, the dark shaft, and the iron bar segments of a grate."""
    m = max(1, ts // 8)
    frame = (px + m, py + m, ts - 2 * m, ts - 2 * m)
    ix, iy = px + 2 * m, py + 2 * m
    iw, ih = ts - 4 * m, ts - 4 * m
    n = 4
    vbars = [((ix + iw * i // n, iy), (ix + iw * i // n, iy + ih))
             for i in range(1, n)]
    hbars = [((ix, iy + ih * i // n), (ix + iw, iy + ih * i // n))
             for i in range(1, n)]
    return {"frame": frame, "shaft": (ix, iy, iw, ih),
            "vbars": vbars, "hbars": hbars}


def draw_grate(target, px: int, py: int, ts: int) -> None:
    if ts < 8:
        pygame.draw.rect(target, IRON, (px + 1, py + 1, ts - 2, ts - 2))
        return
    g = grate_geometry(px, py, ts)
    pygame.draw.rect(target, STONE, g["frame"])
    pygame.draw.rect(target, STONE_DK, g["frame"], max(1, ts // 20))
    pygame.draw.rect(target, SHAFT, g["shaft"])          # the dark way down
    w = max(1, ts // 14)
    for a, b in g["vbars"]:
        pygame.draw.line(target, IRON, a, b, w)
        pygame.draw.line(target, IRON_HI, (a[0], a[1]), (a[0], a[1] + ts // 6), 1)
    for a, b in g["hbars"]:
        pygame.draw.line(target, IRON, a, b, w)
    # a few rust flecks on the bars (deterministic, subtle)
    sx, sy, sw, sh = g["shaft"]
    for k in range(3):
        rx = sx + ((k * 37 + px) % max(1, sw))
        ry = sy + ((k * 53 + py) % max(1, sh))
        pygame.draw.circle(target, RUST, (rx, ry), max(1, ts // 22))


def draw_all(target, engine, view_rect, cam_x, cam_y, ts) -> None:
    """Draw every in-view, explored sewer grate."""
    try:
        from engine.discovery import is_explored
    except Exception:                                    # pragma: no cover
        def is_explored(_e, _x, _y):
            return True
    cols = view_rect.width // ts
    rows = view_rect.height // ts
    for loc in getattr(engine.world, "locations", []):
        if not loc.get_property("sewer_grate"):
            continue
        sx = (loc.x - cam_x)
        sy = (loc.y - cam_y)
        if not (0 <= sx < cols and 0 <= sy < rows):
            continue
        try:
            if not is_explored(engine, loc.x, loc.y):
                continue
        except Exception:
            pass
        draw_grate(target, view_rect.x + sx * ts, view_rect.y + sy * ts, ts)
