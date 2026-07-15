"""2.5D building render (P16.5) — top-down blocks with lit roofs.

Ported from autonomous_world's `renderer_buildings` (height extrusion +
pitched-roof shading), rebuilt the Track-G way we've used since P15.2:
the GEOMETRY and the COLOURS are pure, headless-testable functions, and
a thin `draw_buildings` pass blits them over the flat BUILDING tiles the
main renderer already lays down — so it shades on top of the P15.1 PNG
base without replacing it.

The look: each building tile becomes a little block — its roof lifted up
by a per-KIND height (a wizard's tower stands taller than a farmhouse),
a shaded front wall below it, and the roof split by a ridge line into a
lit northern slope and a shadowed southern one. Cheap, and the single
biggest read-at-a-glance upgrade to the overworld.
"""

from ui.animation import clamp

# base palette (the flat tile is already drawn; these shade the block)
WALL = (120, 92, 66)
ROOF = (150, 70, 55)

# roof height as a fraction of the tile — taller, prouder buildings
_HEIGHT_FRAC = {
    "tower": 0.95, "keep": 0.95, "watchtower": 0.85, "temple": 0.70,
    "hall": 0.60, "tavern": 0.55, "inn": 0.55, "library": 0.55,
    "forge": 0.45, "smithy": 0.45, "shop": 0.45, "lodge": 0.45,
    "farmhouse": 0.40, "stable": 0.40, "bakery": 0.45, "mill": 0.60,
    "shrine": 0.20, "stall": 0.20, "well": 0.15,
}
DEFAULT_FRAC = 0.40


def height_for(kind: str, tile_size: int) -> int:
    """Roof lift, in pixels, for a building kind (min 2)."""
    return max(2, int(_HEIGHT_FRAC.get(kind, DEFAULT_FRAC) * tile_size))


def cube_faces(sx: int, sy: int, ts: int, h: int) -> dict:
    """The two visible faces of a tile-block whose roof is lifted `h`
    pixels: the raised TOP (roof) and the FRONT (south) wall below it."""
    top = [(sx, sy - h), (sx + ts, sy - h),
           (sx + ts, sy + ts - h), (sx, sy + ts - h)]
    front = [(sx, sy + ts - h), (sx + ts, sy + ts - h),
             (sx + ts, sy + ts), (sx, sy + ts)]
    return {"top": top, "front": front}


def roof_faces(sx: int, sy: int, ts: int, h: int) -> dict:
    """The pitched roof: a ridge line across the middle of the top face,
    a lit northern slope above it and a shadowed southern slope below."""
    y0 = sy - h
    y1 = sy + ts - h
    ymid = (y0 + y1) // 2
    return {
        "ridge": [(sx, ymid), (sx + ts, ymid)],
        "lit": [(sx, y0), (sx + ts, y0), (sx + ts, ymid), (sx, ymid)],
        "shadow": [(sx, ymid), (sx + ts, ymid), (sx + ts, y1), (sx, y1)],
    }


# P31.1e — intermediate LEVELS: how many storeys a building shows on its
# front wall (a tower rises in tiers; a cottage is a single storey)
_STOREYS = {
    "tower": 3, "keep": 3, "watchtower": 2, "temple": 2, "hall": 2,
    "inn": 2, "tavern": 2, "library": 2, "mill": 2, "wall_tower": 3,
}
DEFAULT_STOREYS = 1
GUARD_FIGURE = (60, 70, 95)      # a slate-blue watchman atop a tower roof
FLOOR_FRAC = 0.42                # front-wall pixels PER STOREY, as a tile fraction
WINDOW = (54, 46, 40)            # a dark window frame set into the wall
WINDOW_GLASS = (120, 150, 170)   # cool daytime glass (lighting warms it at night)


def storeys_for(kind: str) -> int:
    """How many storeys (front-wall floor bands) a building kind shows."""
    return _STOREYS.get(kind, DEFAULT_STOREYS)


def block_height(kind: str, tile_size: int) -> int:
    """P33.3b storey-DRIVEN lift: a building stands `storeys × floor_px` tall, so
    a 3-storey tower genuinely towers over a 1-storey cottage (the old per-kind
    fraction made every building read as a single storey)."""
    floor_px = max(4, int(tile_size * FLOOR_FRAC))
    return storeys_for(kind) * floor_px


def wall_windows(sx: int, sy: int, ts: int, h: int, storeys: int):
    """Window (x, y, w, h) rects on the front wall — a row per STOREY, so the
    floors read. Empty on a tiny tile. Pure geometry (P33.3b)."""
    if ts < 12 or h < 6 or storeys < 1:
        return []
    eave = sy + ts - h
    band = h / storeys                 # front-wall pixels per storey
    ww = max(2, ts // 6)
    wh = max(2, int(band * 0.42))
    cols = 2 if ts >= 24 else 1
    out = []
    for i in range(storeys):
        wy = int(eave + band * i + band * 0.28)
        for c in range(cols):
            wx = sx + ts * (c + 1) // (cols + 1) - ww // 2
            out.append((int(wx), wy, ww, wh))
    return out


def storey_lines(sx: int, sy: int, ts: int, h: int, storeys: int):
    """The horizontal FLOOR-DIVIDER lines across the front wall of a
    multi-storey block — intermediate levels between the roof eave and the
    ground. Empty for a single-storey building. Pure geometry (P31.1e)."""
    if storeys <= 1:
        return []
    eave = sy + ts - h            # top of the front wall (under the roof)
    ground = sy + ts
    out = []
    for i in range(1, storeys):
        y = eave + (ground - eave) * i // storeys
        out.append(((sx, y), (sx + ts, y)))
    return out


def roof_figure_pos(sx: int, sy: int, ts: int, h: int):
    """The screen point ATOP the block where a roof figure stands — a guard
    on the tower roof (P31.1e). Centred on the lifted roof, a touch north."""
    return (sx + ts // 2, sy - h + ts // 3)


def _scale(color, f: float) -> tuple:
    return tuple(int(clamp(v * f, 0, 255)) for v in color[:3])


def face_colors(wall=WALL, roof=ROOF) -> dict:
    """Lit/shadowed shades for the block's faces."""
    return {
        "roof_lit": _scale(roof, 1.15),
        "roof_shadow": _scale(roof, 0.82),
        "front": _scale(wall, 0.75),
        "ridge": _scale(roof, 1.35),
    }


_STYLES = None
_SHADOW_CACHE = {}


def load_styles() -> dict:
    """P33.3 per-kind building descriptors (roof shape, covering, wall,
    chimneys) from `data/building_styles.json`, cached."""
    global _STYLES
    if _STYLES is None:
        import json
        import os
        path = os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "data", "building_styles.json")
        try:
            with open(path) as fh:
                _STYLES = json.load(fh)
        except Exception:
            _STYLES = {}
    return _STYLES


# the fallback (a town WALL segment / an unmapped building) reads as a flat
# stone rampart rather than a little gabled roof
_DEFAULT_STYLE = {"roof": "flat", "covering": "stone", "wall": "stone",
                  "chimneys": 0, "parapet": True}


def style_for(kind: str) -> dict:
    d = dict(_DEFAULT_STYLE)
    d.update(load_styles().get(kind, {}))
    return d


def _shadow(tile_size: int):
    """A cached soft drop-shadow tile (grounds the block)."""
    s = _SHADOW_CACHE.get(tile_size)
    if s is None:
        import pygame
        s = pygame.Surface((tile_size, tile_size), pygame.SRCALPHA)
        s.fill((0, 0, 0, 70))
        _SHADOW_CACHE[tile_size] = s
    return s


def _kind_at(engine, x: int, y: int):
    loc = engine.world.get_location_at(x, y)
    if loc is None:
        return ""
    # P31.1e: a wall tower reads as a tall, manned tower regardless of its
    # blueprint (it has no interior blueprint, just the marker)
    if (loc.properties or {}).get("wall_tower"):
        return "wall_tower"
    try:
        from world.blueprints import blueprint_for_location
        bp = blueprint_for_location(loc.name)
        return getattr(bp, "kind", "") if bp else ""
    except Exception:
        return ""


def _gate_tiles(engine):
    """Every registered town/castle GATE tile → whether it is barred by an
    alarm (a locked gate). A gate reached in the BUILDING pass is CLOSED (an
    open one is ROAD), so this marks which walls are really shut gateways."""
    tiles = {}
    tg = getattr(engine, "town_gates", None)
    for l in getattr(engine.world, "locations", []):
        for g in (l.get_property("gates") or []):
            pos = (g[0], g[1])
            locked = False
            try:
                if tg is not None:
                    locked = tg.is_locked(pos)
            except Exception:
                pass
            tiles[pos] = locked
    return tiles


def _footprint_map(engine):
    """(wx,wy) -> (loc, kind, is_anchor) for every real (enterable) building —
    so its whole footprint draws as ONE spanning roof (P37.4), not a grid of
    per-tile roofs. The ANCHOR is the south-west tile: drawing the building
    there gives the right 2.5D paint order (its lifted roof overlaps whatever
    lies north)."""
    fmap = {}
    ints = getattr(engine, "interiors", {}) or {}
    for l in getattr(engine.world, "locations", []):
        if l.name not in ints:
            continue
        try:
            from world.blueprints import blueprint_for_location
            bp = blueprint_for_location(l.name)
            kind = getattr(bp, "kind", "") if bp else ""
        except Exception:
            kind = ""
        anchor = (l.x, l.y + l.height - 1)
        for yy in range(l.y, l.y + l.height):
            for xx in range(l.x, l.x + l.width):
                fmap[(xx, yy)] = (l, kind, (xx, yy) == anchor)
    return fmap


def _footprint_explored(engine, loc) -> bool:
    try:
        from engine.discovery import is_explored
    except Exception:
        return True
    for yy in range(loc.y, loc.y + loc.height):
        for xx in range(loc.x, loc.x + loc.width):
            if is_explored(engine, xx, yy):
                return True
    return False


def draw_buildings(target, engine, view_rect, cam_x, cam_y,
                   tile_size) -> None:
    """Real buildings draw as ONE footprint-spanning block (P37.4); loose
    BUILDING tiles (walls) draw per-tile; a shut gate becomes a PORTCULLIS
    (P37.3). Fog-respecting, north-to-south for correct 2.5D overlap."""
    from world.world_map import TerrainType
    wmap = engine.world.map
    gates = _gate_tiles(engine)
    fmap = _footprint_map(engine)
    cols = view_rect.width // tile_size
    rows = view_rect.height // tile_size
    for sy in range(rows):
        for sx in range(cols):
            wx, wy = cam_x + sx, cam_y + sy
            if not (0 <= wx < wmap.width and 0 <= wy < wmap.height):
                continue
            fp = fmap.get((wx, wy))
            if fp is not None:                    # part of a real building
                loc, kind, is_anchor = fp
                if is_anchor and _footprint_explored(engine, loc):
                    _draw_footprint(target, kind, loc, view_rect,
                                    cam_x, cam_y, tile_size)
                continue                          # tiles drawn by the anchor
            if wmap.terrain[wy][wx] != TerrainType.BUILDING:
                continue
            try:
                from engine.discovery import is_explored
                if not is_explored(engine, wx, wy):
                    continue
            except Exception:
                pass
            px = view_rect.x + sx * tile_size
            py = view_rect.y + sy * tile_size
            if (wx, wy) in gates:              # a shut gate reads as a gateway
                # a GATEHOUSE stands a storey taller than the curtain wall, so
                # the barred archway is unmistakable, not a wall with a slot
                _draw_gate(target, px, py, tile_size,
                           block_height("watchtower", tile_size),
                           gates[(wx, wy)])
                continue
            kind = _kind_at(engine, wx, wy)
            h = block_height(kind, tile_size)      # storey-driven (P33.3b)
            _draw_block(target, kind, px, py, tile_size, h)


def _draw_footprint(target, kind, loc, view_rect, cam_x, cam_y, ts) -> None:
    """One real building drawn as a single W×D block with a SPANNING roof
    (P37.4): a drop shadow, a front wall, one gable/hip/flat roof over the whole
    footprint, storey bands + windows along the front, and chimneys."""
    import pygame
    from ui import roof_shapes as rs
    style = style_for(kind)
    px = view_rect.x + (loc.x - cam_x) * ts
    py = view_rect.y + (loc.y - cam_y) * ts
    w = loc.width * ts
    d = loc.height * ts
    h = block_height(kind, ts)
    off = max(1, ts // 7)
    sh = pygame.Surface((w, d), pygame.SRCALPHA)
    sh.fill((0, 0, 0, 70))
    target.blit(sh, (px + off, py + off))
    front = rs.front_color(style["wall"])
    front_quad = rs.span_faces(px, py, w, d, h)["front"]
    pygame.draw.polygon(target, front, front_quad)
    if ts >= 12:                                   # P40.4 masonry/timber texture
        for col, a, b in rs.wall_courses(front_quad, style["wall"], ts):
            pygame.draw.line(target, col, a, b, 1)
    shades = rs.roof_shades(style["covering"])
    rp = rs.span_roof(style["roof"], px, py, w, d, h, style.get("parapet", False))
    for pts, key in rp["polys"]:
        pygame.draw.polygon(target, shades[key], pts)
        if ts >= 12:                               # P40.4 roof tile rows
            for col, a, b in rs.roof_courses(pts, style["covering"], ts):
                pygame.draw.line(target, col, a, b, 1)
    if rp["ridge"]:
        pygame.draw.line(target, shades["ridge"],
                         rp["ridge"][0], rp["ridge"][1], max(1, ts // 20))
    if rp["parapet"]:
        pygame.draw.lines(target, shades["ridge"], True, rp["parapet"], 1)
    fy = py + d - h                                   # top of the front wall
    storeys = max(1, int(h / max(4, int(ts * FLOOR_FRAC))))
    for i in range(1, storeys):                       # floor bands
        by = fy + round(h * i / storeys)
        pygame.draw.line(target, _scale(front, 0.7), (px, by), (px + w, by), 1)
    ww = max(3, ts // 4)                              # a row of windows/floor
    from ui.openings import draw_window, window_shape_for
    shape = window_shape_for(kind)
    for i in range(storeys):
        by = fy + round(h * (i + 0.35) / storeys)
        for c in range(loc.width):
            wx0 = px + c * ts + (ts - ww) // 2
            draw_window(target, (wx0, by, ww, max(2, ww)), shape,
                        frame=WINDOW, glass=WINDOW_GLASS)
    for (cx, cy, cw, ch) in rs.span_chimneys(px, py, w, h, style["chimneys"]):
        pygame.draw.rect(target, rs.CHIMNEY, (cx, cy, cw, ch))
        pygame.draw.rect(target, rs.CHIMNEY_CAP, (cx, cy, cw, max(1, ch // 4)))


def _draw_gate(target, px, py, ts, h, locked: bool = False) -> None:
    """A shut gate as a barred PORTCULLIS in a stone arch (P37.3) — it reads as
    a gateway, not a blank wall; an alarm-locked gate's bars glow iron-red."""
    import pygame
    from ui import gate_shapes as gs
    off = max(1, ts // 7)
    target.blit(_shadow(ts), (px + off, py + off))       # grounds the block
    g = gs.portcullis(px, py, ts, h)
    for key in ("left", "right", "lintel"):
        pygame.draw.rect(target, gs.STONE, g["frame"][key])
    pygame.draw.rect(target, gs.STONE_DARK, g["frame"]["lintel"], 1)
    pygame.draw.rect(target, gs.OPENING, g["opening"])   # the dark recess
    bar_col = gs.LOCKED_IRON if locked else gs.IRON
    vw = max(1, ts // 16)
    for (a, b) in g["bars_v"]:
        pygame.draw.line(target, bar_col, a, b, vw)
    for (a, b) in g["bars_h"]:
        pygame.draw.line(target, gs.IRON_HI, a, b, max(1, ts // 22))


def _draw_block(target, kind, px, py, ts, h) -> None:
    """One building tile as a material-styled 2.5D block (P33.3): a drop
    shadow, a wall front in the wall material, a roof of the descriptor's
    SHAPE and COVERING colour, chimneys, storey lines, and (a wall tower) a
    roof guard."""
    import pygame
    from ui import roof_shapes as rs
    style = style_for(kind)
    off = max(1, ts // 7)
    target.blit(_shadow(ts), (px + off, py + off))     # grounds the block
    front = rs.front_color(style["wall"])
    front_quad = cube_faces(px, py, ts, h)["front"]
    pygame.draw.polygon(target, front, front_quad)
    if ts >= 12:                                   # P40.4 masonry/timber texture
        for col, a, b in rs.wall_courses(front_quad, style["wall"], ts):
            pygame.draw.line(target, col, a, b, 1)
    shades = rs.roof_shades(style["covering"])
    rp = rs.roof_polys(style["roof"], px, py, ts, h, style.get("parapet", False))
    for pts, key in rp["polys"]:
        pygame.draw.polygon(target, shades[key], pts)
        if ts >= 12:                               # P40.4 roof tile rows
            for col, a, b in rs.roof_courses(pts, style["covering"], ts):
                pygame.draw.line(target, col, a, b, 1)
    if rp["ridge"]:
        pygame.draw.line(target, shades["ridge"],
                         rp["ridge"][0], rp["ridge"][1], 1)
    if rp["parapet"]:
        pygame.draw.lines(target, shades["ridge"], True, rp["parapet"], 1)
    storeys = storeys_for(kind)
    for (a, b) in storey_lines(px, py, ts, h, storeys):
        pygame.draw.line(target, _scale(front, 0.7), a, b, 1)
    # per-floor windows make the storeys READ (P33.3b)
    from ui.openings import draw_window, window_shape_for
    shape = window_shape_for(kind)
    for (wx, wy, ww, wh) in wall_windows(px, py, ts, h, storeys):
        draw_window(target, (wx, wy, ww, wh), shape,
                    frame=WINDOW, glass=WINDOW_GLASS)
    for (cx, cy, cw, ch) in rs.chimney_rects(px, py, ts, h, style["chimneys"]):
        pygame.draw.rect(target, rs.CHIMNEY, (cx, cy, cw, ch))
        pygame.draw.rect(target, rs.CHIMNEY_CAP, (cx, cy, cw, max(1, ch // 4)))
    if kind == "wall_tower" and ts >= 12:
        fx, fy = roof_figure_pos(px, py, ts, h)
        pygame.draw.circle(target, GUARD_FIGURE, (fx, fy), max(1, ts // 8))
