"""P41.6 — isometric interior / dungeon render (only when iso mode is on).

Draws a zone grid in 2:1 iso: themed floor DIAMONDS + raised WALL blocks (P39.2
interior_theme colours), furniture as billboarded prop sprites, and the hero +
occupants as iso figures, all depth-sorted. A CUT-AWAY drops the FRONT (south /
east) perimeter walls so the iso camera sees inside; dark levels keep the zone
fog. renderer.render() delegates here when a zone is active and iso is enabled.
"""

import pygame

from ui.iso import IsoProjection


def _proj(ts):
    return IsoProjection(ts, max(8, ts // 2), max(4, ts // 3))


def _scale(c, f):
    return tuple(max(0, min(255, int(v * f))) for v in c[:3])


def _zone_chars(engine, zone):
    out = [(engine.player, tuple(engine.player.position))]
    zname = getattr(zone, "name", None)
    seen = {engine.player.id}
    for npc in engine.npc_manager.npcs.values():
        if npc.id in seen or not (hasattr(npc, "is_active") and
                                  npc.is_active()):
            continue
        meta = getattr(npc, "metadata", {}) or {}
        in_zone = meta.get("zone") == zname
        in_dungeon = (hasattr(zone, "rooms")
                      and npc.id.startswith(("enc_", "tut_"))
                      and 0 <= npc.position[0] < zone.width
                      and 0 <= npc.position[1] < zone.height
                      and meta.get("zone") in (None, zname))
        if in_zone or in_dungeon:
            out.append((npc, tuple(npc.position)))
            seen.add(npc.id)
    for nid, spot in (getattr(zone, "visitors", {}) or {}).items():
        npc = engine.npc_manager.npcs.get(nid)
        if npc is not None and npc.is_active() and nid not in seen:
            out.append((npc, tuple(spot)))
            seen.add(nid)
    return out


def render_zone_iso(target, engine, view_rect, zone, tile_size, sprites) -> None:
    from world.world_map import TerrainType
    from ui import interior_theme, iso_chars
    iso = _proj(tile_size)
    theme = interior_theme.theme_for(zone)
    floor_c = tuple((theme.get("floor") or [90, 90, 96])[:3])
    wall_c = tuple((theme.get("wall") or [120, 120, 130])[:3])
    target.fill(interior_theme.fill_color(theme), view_rect)

    px, py = engine.player.position
    psx, psy = iso.world_to_screen(px, py, 0)
    origin = (view_rect.x + view_rect.width // 2 - psx,
              view_rect.y + view_rect.height // 2 - psy)

    W, H = zone.width, zone.height
    visible = None
    if hasattr(zone, "rooms") or getattr(zone, "dark", False):
        try:
            from world.fov import zone_fov
            visible = zone_fov(zone, (px, py), radius=8)
            explored = getattr(zone, "explored", None) or set()
            visible = set(visible) | set(explored)
        except Exception:
            visible = None

    def _seen(x, y):
        return visible is None or (x, y) in visible or (x, y) == (px, py)

    items = []                                    # (depth_key, tag, payload)
    for wy in range(H):
        for wx in range(W):
            if not _seen(wx, wy):
                continue
            wall = zone.terrain[wy][wx] == TerrainType.BUILDING
            zt = 1.0 if wall else 0.0
            sx, sy = iso.world_to_screen(wx, wy, zt, origin)
            if sx < view_rect.x - tile_size or sx > view_rect.right + tile_size \
                    or sy < view_rect.y - tile_size * 3 \
                    or sy > view_rect.bottom + tile_size:
                continue
            if wall:
                if wy == H - 1 or wx == W - 1:    # cut away the FRONT walls
                    continue
                items.append((iso.depth_key(wx, wy, zt, 1), "wall",
                              (int(sx), int(sy), zt)))
            else:
                items.append((iso.depth_key(wx, wy, 0, 0), "floor",
                              (int(sx), int(sy), wx * 131 + wy)))

    for f in getattr(zone, "furniture", []):
        fx, fy = f.get("x", -1), f.get("y", -1)
        if not (0 <= fx < W and 0 <= fy < H) or not _seen(fx, fy):
            continue
        sx, sy = iso.world_to_screen(fx, fy, 0, origin)
        items.append((iso.depth_key(fx, fy, 0.25, 1), "furn",
                      (f.get("name", "?"), int(sx), int(sy))))

    from ui.body_renderer import update_anim
    from ui.iso_actors import DT, tween_world_pos
    for char, (cx, cy) in _zone_chars(engine, zone):
        if not (0 <= cx < W and 0 <= cy < H) or not _seen(cx, cy):
            continue
        update_anim(char, DT)                     # ISO.8 facing + tween indoors
        fx, fy = tween_world_pos(char, cx, cy)
        sx, sy = iso.world_to_screen(fx, fy, 0, origin)
        items.append((iso.depth_key(fx, fy, 0, 2), "char",
                      (char, int(sx), int(sy))))

    items.sort(key=lambda t: t[0])
    for _, tag, data in items:
        if tag == "floor":
            _floor(target, iso, data, floor_c)
        elif tag == "wall":
            _wall(target, iso, data, wall_c)
        elif tag == "furn":
            _furn(target, sprites, data, tile_size)
        else:
            _char(target, iso_chars, data, tile_size)

    # P41.9 interior light & mood in iso too: darkness with warm firelight pools
    # around braziers/torches + the hero, drifting dust — a crypt reads dark and
    # dank, a home warm (shares the top-down P39.4 model via draw_iso).
    try:
        from ui import interior_light
        interior_light.draw_iso(target, zone, view_rect, iso, origin,
                                tile_size, theme, engine.player.position,
                                visible)
    except Exception:
        pass

    # P41.12 combat popups / hit flashes / death particles on top, in the zone
    try:
        ce = getattr(engine, "combat_effects", None)
        if ce:
            def _cs(x, y):
                sx2, sy2 = iso.world_to_screen(x, y, 0, origin)
                return int(sx2), int(sy2)
            ce.update(1.0 / 30.0)          # AGE them (else sprays never expire)
            ce.draw_with(target, view_rect, _cs, tile_size)
    except Exception:
        pass


def _floor(target, iso, data, col):
    from ui.iso_render import draw_diamond
    sx, sy, seed = data
    draw_diamond(target, iso, sx, sy, col, seed)


def _wall(target, iso, data, col):
    sx, sy, z = data
    for i, face in enumerate(iso.cliff_faces(sx, sy, z)):
        pygame.draw.polygon(target, _scale(col, 0.6 if i == 0 else 0.42),
                            [(int(a), int(b)) for a, b in face])
    dia = [(int(a), int(b)) for a, b in iso.diamond(sx, sy)]
    pygame.draw.polygon(target, _scale(col, 1.1), dia)
    pygame.draw.polygon(target, _scale(col, 0.7), dia, 1)


def _furn(target, sprites, data, tile_size):
    name, sx, sy = data
    # Prefer a baked 3D piece (sarcophagus / pillar / altar / brazier / …);
    # fall back to the flat prop billboard for unmapped names (P41.8).
    try:
        from ui import iso_furniture
        spr3d = iso_furniture.furniture_sprite(name, int(tile_size * 1.5))
    except Exception:
        spr3d = None
    if spr3d is not None:
        w, h = spr3d.get_size()
        target.blit(spr3d, (sx - w // 2, sy - int(h * 0.66)))
        return
    try:
        spr = sprites.furniture(name)
    except Exception:
        return
    spr = pygame.transform.smoothscale(spr, (tile_size, tile_size))
    target.blit(spr, (sx - tile_size // 2, sy - int(tile_size * 0.85)))


def _char(target, iso_chars, data, tile_size):
    char, sx, sy = data
    th = max(6, tile_size // 3)
    sh = pygame.Surface((tile_size, th), pygame.SRCALPHA)
    pygame.draw.ellipse(sh, (0, 0, 0, 95), (0, 0, tile_size, th))
    target.blit(sh, (sx - tile_size // 2, sy - th // 2))
    spr = iso_chars.char_sprite(char, int(tile_size * 1.5))
    w, h = spr.get_size()
    target.blit(spr, (sx - w // 2, sy - int(h * 0.72)))
