"""P33.2 terrain edges + water coastline — end the hard 32px seams.

Two neighbour-aware overlay passes over the flat P33.1 variant tiles, in the
autonomous_world style:
  * a differing LAND terrain fades its colour across the shared seam, so grass
    no longer meets road/forest at a knife edge; and
  * WATER tiles get a depth tint (deep darker, shallow lighter), a gentle
    position-desynced SHIMMER, and FOAM on the sides that face land — so a coast
    reads as a coast.

The classification/geometry is pure and headless-testable (`blend_edges`,
`shore_sides`, `water_depth`, `shimmer_frame`); one thin `draw_terrain_edges`
pass builds & caches the overlay Surfaces and blits them.
"""

# natural LAND terrains that blend into each other (water is handled by foam;
# buildings / walls / caves / bridges keep their hard edge on purpose)
BLENDABLE = {"grass", "forest", "road", "swamp", "farmland", "mountain",
             "rubble", "scorched"}

# the tint each terrain fades across a seam (its P33.1 recipe base shade)
EDGE_COLOR = {
    "grass": (90, 150, 70), "forest": (45, 95, 50), "road": (160, 130, 90),
    "swamp": (55, 72, 54), "farmland": (124, 92, 56), "mountain": (110, 100, 95),
    "rubble": (105, 100, 95), "scorched": (48, 40, 36),
}


def blend_edges(get, wx, wy):
    """The RIGHT/DOWN neighbours (each seam drawn once) that are a DIFFERENT
    blendable land terrain. Returns [(side, neighbour_name), …]."""
    here = get(wx, wy)
    if here not in BLENDABLE:
        return []
    out = []
    r = get(wx + 1, wy)
    if r in BLENDABLE and r != here:
        out.append(("right", r))
    d = get(wx, wy + 1)
    if d in BLENDABLE and d != here:
        out.append(("down", d))
    return out


def shore_sides(get, wx, wy):
    """For a WATER tile, which cardinal sides face non-water land (foam)."""
    if get(wx, wy) != "water":
        return []
    out = []
    for name, dx, dy in (("up", 0, -1), ("down", 0, 1),
                         ("left", -1, 0), ("right", 1, 0)):
        n = get(wx + dx, wy + dy)
        if n is not None and n != "water":
            out.append(name)
    return out


def water_depth(get, wx, wy):
    """'shallow' if any of the 8 neighbours is land, else 'deep' (None if the
    tile itself isn't water)."""
    if get(wx, wy) != "water":
        return None
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            n = get(wx + dx, wy + dy)
            if n is not None and n != "water":
                return "shallow"
    return "deep"


def shimmer_frame(wx, wy, tick, frames=3):
    """Which shimmer frame a water tile shows — desynced by position so the
    whole sea doesn't pulse in lockstep."""
    return (tick + wx + wy) % max(1, frames)


# ---- the thin draw pass (cached overlay Surfaces) -----------------------

_CACHE = {}


def _build_overlays(ts):
    import pygame
    band = max(3, ts // 3)
    edge = {}
    for name, col in EDGE_COLOR.items():
        for side in ("right", "down"):
            s = pygame.Surface((ts, ts), pygame.SRCALPHA)
            for i in range(band):
                a = int(150 * (i + 1) / band)          # 0 at inner → strong at seam
                if side == "right":
                    pygame.draw.line(s, (*col, a),
                                     (ts - band + i, 0), (ts - band + i, ts - 1))
                else:
                    pygame.draw.line(s, (*col, a),
                                     (0, ts - band + i), (ts - 1, ts - band + i))
            edge[(side, name)] = s
    deep = pygame.Surface((ts, ts), pygame.SRCALPHA)
    deep.fill((16, 38, 86, 80))
    shallow = pygame.Surface((ts, ts), pygame.SRCALPHA)
    shallow.fill((120, 180, 214, 46))
    shim = []
    for f in range(3):
        s = pygame.Surface((ts, ts), pygame.SRCALPHA)
        for k in range(2):
            yy = (f * 5 + k * (ts // 2) + 3) % ts
            pygame.draw.line(s, (170, 205, 235, 40),
                             (2, yy), (ts - 3, yy))
        shim.append(s)
    foam = {}
    fb = max(2, ts // 6)
    for side in ("up", "down", "left", "right"):
        s = pygame.Surface((ts, ts), pygame.SRCALPHA)
        for i in range(fb):
            a = int(150 * (fb - i) / fb)
            col = (225, 240, 250, a)
            if side == "up":
                pygame.draw.line(s, col, (0, i), (ts - 1, i))
            elif side == "down":
                pygame.draw.line(s, col, (0, ts - 1 - i), (ts - 1, ts - 1 - i))
            elif side == "left":
                pygame.draw.line(s, col, (i, 0), (i, ts - 1))
            else:
                pygame.draw.line(s, col, (ts - 1 - i, 0), (ts - 1 - i, ts - 1))
        foam[side] = s
    return {"edge": edge, "deep": deep, "shallow": shallow,
            "shim": shim, "foam": foam}


def draw_terrain_edges(target, engine, view_rect, cam_x, cam_y, tile_size):
    """Blit the edge-blend + water-coastline overlays over the flat tiles."""
    import pygame
    from ui.renderer import _TERRAIN_TO_SPRITE
    wmap = engine.world.map

    def get(x, y):
        if 0 <= x < wmap.width and 0 <= y < wmap.height:
            return _TERRAIN_TO_SPRITE.get(wmap.terrain[y][x], "grass")
        return None

    try:
        from engine.discovery import is_explored
    except Exception:
        def is_explored(e, x, y):
            return True

    cache = _CACHE.get(tile_size)
    if cache is None:
        cache = _CACHE[tile_size] = _build_overlays(tile_size)
    cols = view_rect.width // tile_size
    rows = view_rect.height // tile_size
    tick = pygame.time.get_ticks() // 220
    for sy in range(rows):
        for sx in range(cols):
            wx, wy = cam_x + sx, cam_y + sy
            if not (0 <= wx < wmap.width and 0 <= wy < wmap.height):
                continue
            try:
                if not is_explored(engine, wx, wy):
                    continue
            except Exception:
                pass
            dest = (view_rect.x + sx * tile_size, view_rect.y + sy * tile_size)
            for side, neigh in blend_edges(get, wx, wy):
                target.blit(cache["edge"][(side, neigh)], dest)
            if get(wx, wy) == "water":
                depth = water_depth(get, wx, wy)
                target.blit(cache["deep"] if depth == "deep"
                            else cache["shallow"], dest)
                target.blit(cache["shim"][shimmer_frame(wx, wy, tick)], dest)
                for side in shore_sides(get, wx, wy):
                    target.blit(cache["foam"][side], dest)
