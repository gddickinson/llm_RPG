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


def _kind_at(engine, x: int, y: int):
    loc = engine.world.get_location_at(x, y)
    if loc is None:
        return ""
    try:
        from world.blueprints import blueprint_for_location
        bp = blueprint_for_location(loc.name)
        return getattr(bp, "kind", "") if bp else ""
    except Exception:
        return ""


def draw_buildings(target, engine, view_rect, cam_x, cam_y,
                   tile_size) -> None:
    """Draw a raised block over every explored BUILDING tile in view."""
    import pygame
    from world.world_map import TerrainType
    wmap = engine.world.map
    cols = view_rect.width // tile_size
    rows = view_rect.height // tile_size
    colors = face_colors()
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
            h = height_for(_kind_at(engine, wx, wy), tile_size)
            px = view_rect.x + sx * tile_size
            py = view_rect.y + sy * tile_size
            faces = cube_faces(px, py, tile_size, h)
            roof = roof_faces(px, py, tile_size, h)
            pygame.draw.polygon(target, colors["front"], faces["front"])
            pygame.draw.polygon(target, colors["roof_lit"], roof["lit"])
            pygame.draw.polygon(target, colors["roof_shadow"], roof["shadow"])
            pygame.draw.line(target, colors["ridge"],
                             roof["ridge"][0], roof["ridge"][1], 1)
