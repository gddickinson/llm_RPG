"""P41.3 — the ISOMETRIC world render path (behind the LLM_RPG_RENDER=iso
toggle; the top-down renderer stays the default). The engine is untouched — this
is a VIEW only.

Draws the overworld as depth-sorted shaded DIAMONDS (`ui.iso.IsoProjection`),
lifting raised terrain (mountains/buildings) and dropping CLIFF side-faces so the
land reads 3D; water sinks. The player is a simple marker for now (baked 3D
characters + objects are P41.4/P41.5). Fog-of-war respected.
"""

import os

import pygame

from ui.iso import IsoProjection

# per-terrain relief (tile heights, in z units) — mountains rise, water sinks
_HEIGHT = {
    "mountain": 2.2, "mountain2": 2.2, "building": 1.1, "building2": 1.1,
    "forest": 0.4, "forest2": 0.4, "rubble": 0.45, "rubble2": 0.45,
    "cave": 0.2, "water": -0.35, "water2": -0.35, "swamp": -0.1,
    "swamp2": -0.1, "swamp_pool": -0.15, "bridge": 0.15, "bridge2": 0.15,
}


def dispatch(renderer, target, engine, view_rect, zone) -> bool:
    """If iso mode is on, render the active zone (P41.6) or the overworld in
    isometric and return True; else False so the caller keeps the top-down path."""
    if not iso_enabled(engine):
        return False
    try:
        if zone is not None:
            from ui import iso_zone
            iso_zone.render_zone_iso(target, engine, view_rect, zone,
                                     renderer.tile_size, renderer.sprites)
        else:
            render_iso(target, engine, view_rect, renderer.tile_size)
        return True
    except Exception:
        return False


def iso_enabled(engine=None) -> bool:
    """Iso mode on? env LLM_RPG_RENDER=iso overrides; else the in-game
    'Renderer' setting (topdown/iso) in the ',' options overlay (P41.7)."""
    env = os.environ.get("LLM_RPG_RENDER", "").lower()
    if env in ("iso", "topdown"):
        return env == "iso"
    try:
        from engine import settings
        return bool(engine and
                    settings.get_setting(engine.player, "renderer") == "iso")
    except Exception:
        return False


def _scale(c, f):
    return (max(0, min(255, int(c[0] * f))),
            max(0, min(255, int(c[1] * f))),
            max(0, min(255, int(c[2] * f))))


def _terrain_name(terrain) -> str:
    from ui.renderer import _TERRAIN_TO_SPRITE
    return _TERRAIN_TO_SPRITE.get(terrain, "grass")


def _projection(tile_size: int) -> IsoProjection:
    return IsoProjection(tile_w=tile_size, tile_h=max(8, tile_size // 2),
                         z_scale=max(4, tile_size // 3))


def _origin(iso, engine, view_rect):
    """Screen origin that centres the player's iso tile in the view."""
    px, py = engine.player.position
    z = _HEIGHT.get(_terrain_name(engine.world.map.terrain[py][px]), 0.0)
    psx, psy = iso.world_to_screen(px, py, z)
    return (view_rect.x + view_rect.width // 2 - psx,
            view_rect.y + view_rect.height // 2 - psy)


def _tile_box(iso, view_rect, origin, wmap, pad=3):
    corners = [(view_rect.x, view_rect.y), (view_rect.right, view_rect.y),
               (view_rect.x, view_rect.bottom),
               (view_rect.right, view_rect.bottom)]
    ts = [iso.screen_to_tile(cx, cy, origin) for cx, cy in corners]
    xs = [t[0] for t in ts]
    ys = [t[1] for t in ts]
    return (max(0, min(xs) - pad), min(wmap.width, max(xs) + pad + 1),
            max(0, min(ys) - pad - 4), min(wmap.height, max(ys) + pad + 1))


def render_iso(target, engine, view_rect, tile_size) -> None:
    """Draw the overworld in isometric into `target`."""
    from ui.sprite_loader import PALETTE
    try:
        from engine.discovery import is_explored
    except Exception:
        is_explored = None
    wmap = engine.world.map
    px, py = engine.player.position
    iso = _projection(tile_size)
    origin = _origin(iso, engine, view_rect)
    target.fill((22, 22, 30), view_rect)

    from ui import iso_objects
    anchors = _building_anchors(engine)
    x0, x1, y0, y1 = _tile_box(iso, view_rect, origin, wmap)

    # ONE back-to-front pass over terrain + objects, keyed by iso depth so a
    # building/tree correctly occludes what lies behind it (P41.4)
    items = []                                  # (depth_key, tag, payload)
    for wy in range(y0, y1):
        for wx in range(x0, x1):
            if is_explored is not None and (wx, wy) != (px, py) \
                    and not is_explored(engine, wx, wy):
                continue
            name = _terrain_name(wmap.terrain[wy][wx])
            z = _HEIGHT.get(name, 0.0)
            sx, sy = iso.world_to_screen(wx, wy, z, origin)
            if sx < view_rect.x - tile_size or sx > view_rect.right + tile_size \
                    or sy < view_rect.y - tile_size * 3 \
                    or sy > view_rect.bottom + tile_size:
                continue
            items.append((iso.depth_key(wx, wy, z, 0), "tile",
                          (int(sx), int(sy), PALETTE.get(name, (90, 150, 70)),
                           z, wx, wy)))
            if name in ("forest", "forest2"):
                items.append((iso.depth_key(wx, wy, z, 1), "obj",
                              (iso_objects.tree_sprite(int(tile_size * 1.5)),
                               int(sx), int(sy))))
            kind = anchors.get((wx, wy))
            if kind is not None:
                bs = int(tile_size * 2.2)
                items.append((iso.depth_key(wx, wy, 1.1, 1), "obj",
                              (iso_objects.building_sprite(kind, bs),
                               int(sx), int(sy))))
    # characters (hero + visible NPCs) in the same depth order (layer 2)
    for char in _visible_chars(engine):
        cx, cy = char.position
        if not (x0 <= cx < x1 and y0 <= cy < y1):
            continue
        if is_explored is not None and char is not engine.player \
                and not is_explored(engine, cx, cy):
            continue
        cz = _HEIGHT.get(_terrain_name(wmap.terrain[cy][cx]), 0.0)
        sx, sy = iso.world_to_screen(cx, cy, cz, origin)
        items.append((iso.depth_key(cx, cy, cz, 2), "char",
                      (char, int(sx), int(sy))))
    items.sort(key=lambda t: t[0])

    for _, tag, data in items:
        if tag == "tile":
            _draw_tile(target, iso, data)
        elif tag == "obj":
            _blit_object(target, data)
        else:
            _draw_char(target, data, tile_size)


def _visible_chars(engine):
    """Hero + active NPCs the top-down view would show (not wall-hidden)."""
    out = [engine.player]
    try:
        from engine.presence import hidden_by_walls
    except Exception:
        hidden_by_walls = None
    for npc in engine.npc_manager.npcs.values():
        if not (hasattr(npc, "is_active") and npc.is_active()):
            continue
        if hidden_by_walls is not None and hidden_by_walls(engine, npc):
            continue
        out.append(npc)
    return out


def _draw_char(target, data, tile_size):
    from ui import iso_chars
    char, sx, sy = data
    th = max(6, tile_size // 3)
    sh = pygame.Surface((tile_size, th), pygame.SRCALPHA)
    pygame.draw.ellipse(sh, (0, 0, 0, 95), (0, 0, tile_size, th))
    target.blit(sh, (sx - tile_size // 2, sy - th // 2))     # contact shadow
    spr = iso_chars.char_sprite(char, int(tile_size * 1.5))
    w, h = spr.get_size()
    target.blit(spr, (sx - w // 2, sy - int(h * 0.72)))


def draw_diamond(target, iso, sx, sy, top, seed=0):
    """A tile top-face diamond, P41.7 SHADED (top-lit, lower-shade) + a few
    deterministic texture flecks so the iso ground reads less flat."""
    dia = [(int(a), int(b)) for a, b in iso.diamond(sx, sy)]
    t, r, b, l = dia
    pygame.draw.polygon(target, top, dia)
    pygame.draw.polygon(target, _scale(top, 1.07), [t, r, l])   # sky-lit top
    pygame.draw.polygon(target, _scale(top, 0.9), [l, r, b])    # lower shade
    h = (seed * 2654435761) & 0x7fffffff
    hw, hh = max(1, iso.tw // 5), max(1, iso.th // 5)
    for i in range(3):
        h = (h * 1103515245 + 12345) & 0x7fffffff
        dx = (h % (2 * hw + 1)) - hw
        h = (h * 1103515245 + 12345) & 0x7fffffff
        dy = (h % (2 * hh + 1)) - hh
        target.fill(_scale(top, 1.2 if i % 2 else 0.78),
                    (sx + dx, sy + dy, 2, 2))
    pygame.draw.polygon(target, _scale(top, 0.68), dia, 1)      # edge


def _draw_tile(target, iso, data):
    sx, sy, top, z, wx, wy = data
    for i, face in enumerate(iso.cliff_faces(sx, sy, z)):       # sides first
        pygame.draw.polygon(target, _scale(top, 0.55 if i == 0 else 0.4),
                            [(int(a), int(b)) for a, b in face])
    draw_diamond(target, iso, sx, sy, top, wx * 131 + wy)


def _blit_object(target, data):
    """Blit a baked 3D sprite so its ground-point sits on the tile centre, with
    a soft contact shadow (P41.7)."""
    spr, sx, sy = data
    w, h = spr.get_size()
    sw = int(w * 0.55)
    shh = max(3, sw // 3)
    sh = pygame.Surface((sw, shh), pygame.SRCALPHA)
    pygame.draw.ellipse(sh, (0, 0, 0, 70), (0, 0, sw, shh))
    target.blit(sh, (sx - sw // 2, sy - shh // 2))
    target.blit(spr, (sx - w // 2, sy - int(h * 0.72)))


def _building_anchors(engine):
    """{front-centre tile: kind} for each enterable building (P41.4)."""
    out = {}
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
            kind = getattr(bp, "kind", "") or "home" if bp else "home"
        out[(loc.x + loc.width // 2, loc.y + loc.height - 1)] = kind
    return out


