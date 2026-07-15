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


def iso_enabled(engine=None) -> bool:
    """Iso mode on? env LLM_RPG_RENDER=iso, or a player 'iso' setting."""
    if os.environ.get("LLM_RPG_RENDER", "").lower() == "iso":
        return True
    try:
        from engine import settings
        return bool(engine and settings.enabled(engine.player, "iso"))
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
                           z)))
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
    # the hero, in the same depth order
    pz = _HEIGHT.get(_terrain_name(wmap.terrain[py][px]), 0.0)
    items.append((iso.depth_key(px, py, pz, 2), "player", None))
    items.sort(key=lambda t: t[0])

    for _, tag, data in items:
        if tag == "tile":
            _draw_tile(target, iso, data)
        elif tag == "obj":
            _blit_object(target, data)
        else:
            _draw_player(target, iso, engine, origin, tile_size)


def _draw_tile(target, iso, data):
    sx, sy, top, z = data
    for i, face in enumerate(iso.cliff_faces(sx, sy, z)):       # sides first
        pygame.draw.polygon(target, _scale(top, 0.55 if i == 0 else 0.4),
                            [(int(a), int(b)) for a, b in face])
    dia = [(int(a), int(b)) for a, b in iso.diamond(sx, sy)]
    pygame.draw.polygon(target, top, dia)
    pygame.draw.polygon(target, _scale(top, 0.72), dia, 1)      # tile edge


def _blit_object(target, data):
    """Blit a baked 3D sprite so its ground-point sits on the tile centre."""
    spr, sx, sy = data
    w, h = spr.get_size()
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


def _draw_player(target, iso, engine, origin, tile_size):
    px, py = engine.player.position
    z = _HEIGHT.get(_terrain_name(engine.world.map.terrain[py][px]), 0.0)
    sx, sy = iso.world_to_screen(px, py, z, origin)
    th = max(8, tile_size // 2)
    foot = (int(sx), int(sy))
    sh = pygame.Surface((tile_size, th), pygame.SRCALPHA)
    pygame.draw.ellipse(sh, (0, 0, 0, 90), (0, 0, tile_size, th))
    target.blit(sh, (foot[0] - tile_size // 2, foot[1] - th // 2))
    pygame.draw.rect(target, (70, 90, 160),
                     (foot[0] - tile_size // 8, foot[1] - th,
                      tile_size // 4, th))
    pygame.draw.circle(target, (232, 196, 160),
                       (foot[0], foot[1] - th), max(3, tile_size // 8))
