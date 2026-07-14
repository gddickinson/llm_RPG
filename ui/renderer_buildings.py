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


def draw_buildings(target, engine, view_rect, cam_x, cam_y,
                   tile_size) -> None:
    """Draw a raised block over every explored BUILDING tile in view."""
    from world.world_map import TerrainType
    wmap = engine.world.map
    cols = view_rect.width // tile_size
    rows = view_rect.height // tile_size
    for sy in range(rows):
        for sx in range(cols):
            wx, wy = cam_x + sx, cam_y + sy
            if not (0 <= wx < wmap.width and 0 <= wy < wmap.height):
                continue
            if wmap.terrain[wy][wx] != TerrainType.BUILDING:
                continue
            try:
                from engine.discovery import is_explored
                if not is_explored(engine, wx, wy):
                    continue
            except Exception:
                pass
            kind = _kind_at(engine, wx, wy)
            h = block_height(kind, tile_size)      # storey-driven (P33.3b)
            px = view_rect.x + sx * tile_size
            py = view_rect.y + sy * tile_size
            _draw_block(target, kind, px, py, tile_size, h)


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
    pygame.draw.polygon(target, front, cube_faces(px, py, ts, h)["front"])
    shades = rs.roof_shades(style["covering"])
    rp = rs.roof_polys(style["roof"], px, py, ts, h, style.get("parapet", False))
    for pts, key in rp["polys"]:
        pygame.draw.polygon(target, shades[key], pts)
    if rp["ridge"]:
        pygame.draw.line(target, shades["ridge"],
                         rp["ridge"][0], rp["ridge"][1], 1)
    if rp["parapet"]:
        pygame.draw.lines(target, shades["ridge"], True, rp["parapet"], 1)
    storeys = storeys_for(kind)
    for (a, b) in storey_lines(px, py, ts, h, storeys):
        pygame.draw.line(target, _scale(front, 0.7), a, b, 1)
    # per-floor windows make the storeys READ (P33.3b)
    for (wx, wy, ww, wh) in wall_windows(px, py, ts, h, storeys):
        pygame.draw.rect(target, WINDOW, (wx, wy, ww, wh))
        pygame.draw.rect(target, WINDOW_GLASS, (wx, wy, ww, max(1, wh - 1)))
    for (cx, cy, cw, ch) in rs.chimney_rects(px, py, ts, h, style["chimneys"]):
        pygame.draw.rect(target, rs.CHIMNEY, (cx, cy, cw, ch))
        pygame.draw.rect(target, rs.CHIMNEY_CAP, (cx, cy, cw, max(1, ch // 4)))
    if kind == "wall_tower" and ts >= 12:
        fx, fy = roof_figure_pos(px, py, ts, h)
        pygame.draw.circle(target, GUARD_FIGURE, (fx, fy), max(1, ts // 8))
