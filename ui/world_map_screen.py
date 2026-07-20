"""GAP.4 the openable WORLD MAP (M key) — a full-screen schematic.

A huge world had only a corner minimap. This draws the whole map over
the persistent EXPLORED mask (fog of war respected): terrain at a glance,
discovered landmarks labelled, the player + party marked, waystones
picked out. Pure helpers (`notable_locations`, `terrain_color`) are
headless-testable; `draw_world_map` is a thin pygame pass.
"""

import pygame

from world.world_map import TerrainType

TERRAIN_COLORS = {
    TerrainType.GRASS: (90, 150, 70),
    TerrainType.FOREST: (35, 90, 45),
    TerrainType.MOUNTAIN: (110, 100, 95),
    TerrainType.WATER: (45, 100, 180),
    TerrainType.ROAD: (160, 130, 90),
    TerrainType.BUILDING: (140, 100, 60),
    TerrainType.CAVE: (30, 30, 35),
    TerrainType.SWAMP: (62, 78, 52),
    TerrainType.FARMLAND: (124, 92, 56),
    TerrainType.RUBBLE: (105, 100, 95),
    TerrainType.SCORCHED: (48, 40, 36),
}

# a landmark worth a label on the map (kind or name keyword)
_MAJOR_KINDS = {"settlement", "village", "town", "city", "castle",
                "guildhall", "stable", "waystone", "cathedral", "temple",
                "colosseum", "ruin", "dungeon"}
_MAJOR_WORDS = ("village", "town", "castle", "keep", "guild", "waystone",
                "cathedral", "colosseum", "ruin", "vault", "hollow",
                "camp", "stair", "delve", "grate", "cleft", "adit",
                "warren", "den", "roost", "hall", "stable")


def terrain_color(terrain):
    return TERRAIN_COLORS.get(terrain, (55, 55, 60))


def _kind_of(loc):
    props = getattr(loc, "properties", None) or {}
    return (props.get("kind") or props.get("type") or "").lower()


def _is_major(name, kind):
    if kind in _MAJOR_KINDS:
        return True
    low = name.lower()
    return any(w in low for w in _MAJOR_WORDS)


def notable_locations(engine):
    """Explored, named landmarks worth marking: list of
    (x, y, name, is_major, is_waystone). Fog-respecting."""
    from engine import discovery
    out, seen = [], set()
    for loc in getattr(engine.world, "locations", []):
        name = getattr(loc, "name", "") or ""
        if not name or name in seen:
            continue
        cx = loc.x + getattr(loc, "width", 1) // 2
        cy = loc.y + getattr(loc, "height", 1) // 2
        try:
            if not discovery.is_explored(engine, cx, cy):
                continue
        except Exception:
            pass
        kind = _kind_of(loc)
        seen.add(name)
        out.append((cx, cy, name, _is_major(name, kind),
                    kind == "waystone" or "waystone" in name.lower()))
    return out


def _fog(engine):
    try:
        from engine import discovery
        return discovery.visible_set(engine), discovery._explored(engine)
    except Exception:
        return None


def _font(size):
    try:
        if not pygame.font.get_init():
            pygame.font.init()
        return pygame.font.SysFont("consolas,menlo,monospace", size)
    except Exception:
        return None


def draw_world_map(gui):
    screen = gui.screen
    engine = gui.engine
    wmap = engine.world.map
    W, H = screen.get_size()
    screen.fill((10, 10, 14))

    title_f = _font(26)
    small_f = _font(13)
    if title_f is not None:
        t = title_f.render("World Map", True, (235, 225, 180))
        screen.blit(t, ((W - t.get_width()) // 2, 12))

    margin = 40
    top = 48
    avail_w = W - 2 * margin
    avail_h = H - top - margin - 24
    scale = max(1, min(avail_w // max(1, wmap.width),
                       avail_h // max(1, wmap.height)))
    mapw, maph = wmap.width * scale, wmap.height * scale
    ox = (W - mapw) // 2
    oy = top + (avail_h - maph) // 2

    # paint terrain into a 1px-per-tile surface, then scale up
    fog = _fog(engine)
    from ui.hud_style import fog_terrain_color
    surf = pygame.Surface((wmap.width, wmap.height))
    for y in range(wmap.height):
        row = wmap.terrain[y]
        for x in range(wmap.width):
            base = terrain_color(row[x])
            if fog is None:
                color = base
            else:
                vis, exp = fog
                color = fog_terrain_color(base, (x, y) in vis, (x, y) in exp)
            surf.set_at((x, y), color)
    screen.blit(pygame.transform.scale(surf, (mapw, maph)), (ox, oy))
    pygame.draw.rect(screen, (60, 60, 70), (ox, oy, mapw, maph), 1)

    def to_screen(tx, ty):
        return ox + tx * scale + scale // 2, oy + ty * scale + scale // 2

    # landmarks — dots always; labels for waystones/major first, and skip a
    # label that would overlap one already placed (declutter the town core)
    marks = notable_locations(engine)
    for lx, ly, name, major, waystone in marks:
        sx, sy = to_screen(lx, ly)
        if waystone:
            pygame.draw.circle(screen, (120, 220, 255), (sx, sy), 4)
            pygame.draw.circle(screen, (255, 255, 255), (sx, sy), 4, 1)
        elif major:
            pygame.draw.circle(screen, (250, 220, 120), (sx, sy), 3)
        else:
            pygame.draw.circle(screen, (200, 200, 200), (sx, sy), 2)
    if small_f is not None:
        placed = []
        labelled = [m for m in marks if m[3] or m[4]]
        labelled.sort(key=lambda m: (not m[4], not m[3]))   # waystone, major
        for lx, ly, name, major, waystone in labelled:
            sx, sy = to_screen(lx, ly)
            lbl = small_f.render(name, True, (235, 235, 215))
            rect = pygame.Rect(sx + 6, sy - 6, lbl.get_width() + 4,
                               lbl.get_height())
            if any(rect.colliderect(r) for r in placed):
                continue                                 # would overlap — dot only
            placed.append(rect)
            bg = pygame.Surface((rect.width, rect.height))
            bg.set_alpha(150)
            bg.fill((0, 0, 0))
            screen.blit(bg, rect.topleft)
            screen.blit(lbl, (rect.x + 2, rect.y))

    # party then the player on top
    try:
        for m in engine.companion_manager.companions:
            if m.is_active():
                sx, sy = to_screen(*m.position)
                pygame.draw.circle(screen, (120, 255, 180), (sx, sy), 3)
    except Exception:
        pass
    px, py = engine.player.position
    sx, sy = to_screen(px, py)
    pygame.draw.circle(screen, (255, 240, 90), (sx, sy), 5)
    pygame.draw.circle(screen, (0, 0, 0), (sx, sy), 5, 1)

    if small_f is not None:
        legend = ("You  •  landmark  •  waystone      "
                  "[M] or [Esc] to close")
        l = small_f.render(legend, True, (200, 200, 190))
        screen.blit(l, ((W - l.get_width()) // 2, H - 22))
