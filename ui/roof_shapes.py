"""P33.3 building materials + roof shapes — pure geometry & colour.

The old renderer drew every building as the same red gable ridge. building-gen's
insight is that a building's LOOK is a few descriptors: a roof SHAPE (gable / hip
/ flat-with-parapet), a COVERING that fixes the roof colour (thatch gold, clay
terracotta, slate grey, wood shingle, stone, cloth) and a WALL material. This
module is the pure, headless-testable core: colour tables + the roof polygon sets
for a lifted tile-block. `renderer_buildings` reads `data/building_styles.json`,
looks the colours up here, and blits the polygons this returns.
"""

COVERINGS = {
    "thatch":  (176, 146, 88),
    "clay":    (150, 82, 60),
    "shingle": (118, 94, 70),
    "slate":   (92, 100, 112),
    "stone":   (124, 120, 112),
    "cloth":   (184, 172, 150),
    "lead":    (108, 112, 120),
}
WALLS = {
    "stone":  (152, 146, 136),
    "timber": (142, 112, 80),
    "brick":  (152, 96, 82),
    "wood":   (140, 110, 78),
}
DEFAULT_COVERING = (150, 82, 60)
DEFAULT_WALL = (140, 110, 78)
CHIMNEY = (86, 74, 66)
CHIMNEY_CAP = (120, 106, 96)


def covering_color(name):
    return COVERINGS.get(name, DEFAULT_COVERING)


def wall_color(name):
    return WALLS.get(name, DEFAULT_WALL)


def _scale(c, f):
    return tuple(max(0, min(255, int(v * f))) for v in c[:3])


def roof_shades(covering):
    """Lit / shadow / mid / ridge shades for a covering."""
    base = covering_color(covering)
    return {"lit": _scale(base, 1.15), "shadow": _scale(base, 0.82),
            "mid": _scale(base, 0.98), "ridge": _scale(base, 1.35)}


def front_color(wall):
    return _scale(wall_color(wall), 0.72)


def gable_polys(sx, sy, ts, h):
    """A ridge across the middle: a lit north slope + a shadowed south slope."""
    y0, y1 = sy - h, sy + ts - h
    ymid = (y0 + y1) // 2
    return {"polys": [([(sx, y0), (sx + ts, y0), (sx + ts, ymid), (sx, ymid)],
                       "lit"),
                      ([(sx, ymid), (sx + ts, ymid), (sx + ts, y1), (sx, y1)],
                       "shadow")],
            "ridge": [(sx, ymid), (sx + ts, ymid)], "parapet": None}


def hip_polys(sx, sy, ts, h):
    """Four slopes meeting at an apex — a pyramidal hip (the formal look)."""
    y0, y1 = sy - h, sy + ts - h
    ax, ay = sx + ts // 2, (y0 + y1) // 2
    tl, tr, br, bl = (sx, y0), (sx + ts, y0), (sx + ts, y1), (sx, y1)
    return {"polys": [([tl, tr, (ax, ay)], "lit"),
                      ([tr, br, (ax, ay)], "shadow"),
                      ([br, bl, (ax, ay)], "shadow"),
                      ([bl, tl, (ax, ay)], "mid")],
            "ridge": None, "parapet": None}


def flat_polys(sx, sy, ts, h, parapet=False):
    """A flat top; a parapet rim if the kind wants one (towers/keeps)."""
    y0, y1 = sy - h, sy + ts - h
    top = [(sx, y0), (sx + ts, y0), (sx + ts, y1), (sx, y1)]
    return {"polys": [(top, "mid")], "ridge": None,
            "parapet": top if parapet else None}


def roof_polys(shape, sx, sy, ts, h, parapet=False):
    if shape == "hip":
        return hip_polys(sx, sy, ts, h)
    if shape == "flat":
        return flat_polys(sx, sy, ts, h, parapet)
    return gable_polys(sx, sy, ts, h)


def chimney_rects(sx, sy, ts, h, n):
    """Up to two chimney (x, y, w, h) rects standing on the roof top."""
    if n <= 0 or ts < 12:
        return []
    top_y = sy - h
    cw = max(2, ts // 7)
    ch = max(3, ts // 4)
    out = []
    for i in range(min(int(n), 2)):
        cx = sx + ts // 3 + i * (ts // 3)
        out.append((cx, top_y - ch, cw, ch))
    return out
