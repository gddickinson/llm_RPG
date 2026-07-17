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
from ui import overworld_scatter as _scatter

# per-terrain relief (tile heights, in z units) — mountains rise, water sinks
_HEIGHT = {
    "mountain": 2.2, "mountain2": 2.2, "building": 1.1, "building2": 1.1,
    "forest": 0.4, "forest2": 0.4, "rubble": 0.45, "rubble2": 0.45,
    "cave": 0.2, "water": -0.35, "water2": -0.35, "swamp": -0.1,
    "swamp2": -0.1, "swamp_pool": -0.15, "bridge": 0.15, "bridge2": 0.15,
}


def _variant_materials(kind, wx, wy):
    """ISO.1 the per-building (covering, wall) variant — buildings of a kind
    differ (thatch/tile/slate × timber/stone/brick), seeded by world position."""
    try:
        from ui.building_variety import variant_style
        from ui.renderer_buildings import style_for
        s = variant_style(style_for(kind), kind, wx, wy)
        return s.get("covering"), s.get("wall")
    except Exception:
        return None, None


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
            render_iso(target, engine, view_rect, renderer.tile_size,
                       getattr(renderer, "sprites", None))
            # P41.10 day-night + weather parity for the iso OVERWORLD (interiors
            # keep their own P41.9 light); reuse the renderer's persistent
            # weather overlay so particles animate frame-to-frame.
            try:
                from ui import sky_overlay
                if getattr(renderer, "_weather_overlay", None) is None:
                    from ui.weather_overlay import WeatherOverlay
                    renderer._weather_overlay = WeatherOverlay()
                sky_overlay.apply(target, view_rect, engine,
                                  renderer._weather_overlay)
                iso = _projection(renderer.tile_size)
                origin = _origin(iso, engine, view_rect)
                draw_combat_iso(target, engine, view_rect, iso, origin,
                                engine.world.map, renderer.tile_size)
            except Exception:
                pass
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


def render_iso(target, engine, view_rect, tile_size, sprites=None) -> None:
    """Draw the overworld in isometric into `target`."""
    from ui.sprite_loader import PALETTE
    try:
        from engine.discovery import is_explored
    except Exception:
        is_explored = None
    if sprites is None:
        sprites = _get_sprites(tile_size)
    wmap = engine.world.map
    px, py = engine.player.position
    iso = _projection(tile_size)
    origin = _origin(iso, engine, view_rect)
    target.fill((22, 22, 30), view_rect)

    from ui import iso_objects, iso_structures
    binfos = iso_structures.building_infos(engine)          # ISO.15 footprints
    footprints = iso_structures.footprint_tiles(engine)
    x0, x1, y0, y1 = _tile_box(iso, view_rect, origin, wmap)
    # P41.11 gameplay parity: dropped loot, fire/oil/water pools, projectiles,
    # and the ranged reticle must show in iso too (they were top-down-only)
    ground_items = getattr(engine.world, "ground_items", {}) or {}
    try:
        surfaces = engine.surfaces_layer.surfaces
    except Exception:
        surfaces = {}
    clk = pygame.time.get_ticks() / 1000.0

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
            if (wx, wy) in footprints:               # ISO.15 building footprint
                name, z = "grass", 0.0               # → flat ground under the box
            sx, sy = iso.world_to_screen(wx, wy, z, origin)
            if sx < view_rect.x - tile_size or sx > view_rect.right + tile_size \
                    or sy < view_rect.y - tile_size * 3 \
                    or sy > view_rect.bottom + tile_size:
                continue
            items.append((iso.depth_key(wx, wy, z, 0), "tile",
                          (int(sx), int(sy), PALETTE.get(name, (90, 150, 70)),
                           z, wx, wy, name)))
            if name in ("forest", "forest2"):
                items.append((iso.depth_key(wx, wy, z, 1), "obj",
                              (iso_objects.tree_sprite(int(tile_size * 1.5)),
                               int(sx), int(sy))))
            si = surfaces.get((wx, wy))
            if si:                                     # fire / oil / water pool
                items.append((iso.depth_key(wx, wy, z, 0.5), "surface",
                              (si.get("kind", "water"), int(sx), int(sy), clk)))
            gi = ground_items.get((wx, wy))
            if gi:                                     # dropped loot / a body
                nm = gi[0].name if hasattr(gi[0], "name") else str(gi[0])
                items.append((iso.depth_key(wx, wy, z, 0.6), "item",
                              (sprites.item(nm), int(sx), int(sy))))
            sp = _scatter.prop_at(wx, wy, name)        # P39.6b decorative props
            if sp:
                items.append((iso.depth_key(wx, wy, z, 0.9), "scatter",
                              (sp, int(sx), int(sy))))
    # characters (hero + visible NPCs) in the same depth order (layer 2)
    from ui.body_renderer import update_anim
    from ui.iso_actors import DT, tween_world_pos, visible_chars
    for char in visible_chars(engine):
        cx, cy = char.position
        if not (x0 <= cx < x1 and y0 <= cy < y1):
            continue
        if is_explored is not None and char is not engine.player \
                and not is_explored(engine, cx, cy):
            continue
        # ISO.8: advance the anim (writes the movement FACING + the tile-to-tile
        # TWEEN), then draw at the FRACTIONAL tween position so the step SLIDES
        # instead of teleporting — the smooth-movement parity the top-down view
        # already has (George: "movements are a bit jerky, they wait between
        # tiles"). Height still samples the logical tile.
        update_anim(char, DT)
        fx, fy = tween_world_pos(char, cx, cy)
        cz = _HEIGHT.get(_terrain_name(wmap.terrain[cy][cx]), 0.0)
        sx, sy = iso.world_to_screen(fx, fy, cz, origin)
        items.append((iso.depth_key(fx, fy, cz, 2), "char",
                      (char, int(sx), int(sy))))
    # the skilling-pet follower (P41.12), depth-sorted just behind the cast
    try:
        pet = engine.pet_system.active_pet()
        ppos = engine.pet_system.follow_pos
        if pet and ppos and x0 <= ppos[0] < x1 and y0 <= ppos[1] < y1 \
                and (is_explored is None or is_explored(engine, *ppos)):
            pz = _HEIGHT.get(_terrain_name(wmap.terrain[ppos[1]][ppos[0]]), 0.0)
            sx, sy = iso.world_to_screen(ppos[0], ppos[1], pz, origin)
            items.append((iso.depth_key(ppos[0], ppos[1], pz, 1.9), "pet",
                          (pet, int(sx), int(sy))))
    except Exception:
        pass
    # the trailing mount (P28.2d)
    try:
        from engine.mounts import mount_position, active_mount
        mp = mount_position(engine)
        if mp and x0 <= mp[0] < x1 and y0 <= mp[1] < y1 \
                and (is_explored is None or is_explored(engine, *mp)):
            mz = _HEIGHT.get(_terrain_name(wmap.terrain[mp[1]][mp[0]]), 0.0)
            sx, sy = iso.world_to_screen(mp[0], mp[1], mz, origin)
            items.append((iso.depth_key(mp[0], mp[1], mz, 1.95), "mount",
                          (active_mount(engine.player) or "horse",
                           int(sx), int(sy))))
    except Exception:
        pass
    # ISO.15 footprint-spanning building boxes, keyed on the FRONT tile so they
    # occlude what's behind and are occluded by what's in front (explored-gated)
    for info in binfos:
        bx0, by0, bx1, by1, kind = info[:5]
        name = info[5] if len(info) > 5 else ""
        if bx1 < x0 or bx0 > x1 or by1 < y0 or by0 > y1:
            continue
        if is_explored is not None and not is_explored(engine, bx0, by0):
            continue
        cov, wl = _variant_materials(kind, bx0, by0)
        door_st = iso_structures.door_state(engine, name)
        items.append((iso.depth_key(bx1, by1, 1.5, 1.3), "building",
                      (info, cov, wl, door_st)))
    items.sort(key=lambda t: t[0])

    for _, tag, data in items:
        if tag == "tile":
            _draw_tile(target, iso, data)
        elif tag == "surface":
            _draw_surface(target, iso, data)
        elif tag == "item":
            _draw_grounditem(target, data)
        elif tag == "scatter":
            _draw_scatter(target, data, tile_size)
        elif tag == "pet":
            _draw_pet_iso(target, data, tile_size)
        elif tag == "mount":
            _draw_mount_iso(target, data, tile_size)
        elif tag == "obj":
            _blit_object(target, data)
        elif tag == "building":
            info, cov, wl, door_st = data
            iso_structures.draw_building(target, iso, origin, info, cov, wl,
                                         door_st)
        else:
            _draw_char(target, data, tile_size)

    # transient overlays on top of the scene (matches the top-down order:
    # before the sky_overlay darkness/weather that dispatch() adds after)
    _draw_iso_projectiles(target, engine, iso, origin, wmap, tile_size)
    _draw_iso_reticle(target, engine, iso, origin, wmap, tile_size,
                      x0, x1, y0, y1)


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


def draw_diamond(target, iso, sx, sy, top, seed=0, name=None, wx=0, wy=0):
    """A tile top-face diamond. ISO.2: a real `tile_variants` TEXTURE clipped to
    the diamond when the terrain has a recipe; else the P41.7 flat shaded
    diamond + a few deterministic flecks."""
    dia = [(int(a), int(b)) for a, b in iso.diamond(sx, sy)]
    if name is not None:
        from ui import iso_tiles
        tex = iso_tiles.tile_diamond(name, wx, wy, iso.tw, iso.th)
        if tex is not None:
            target.blit(tex, (int(sx - iso.tw / 2), int(sy - iso.th / 2)))
            pygame.draw.polygon(target, _scale(top, 0.68), dia, 1)   # edge
            return
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
    sx, sy, top, z, wx, wy = data[:6]
    name = data[6] if len(data) > 6 else None
    for i, face in enumerate(iso.cliff_faces(sx, sy, z)):       # sides first
        pygame.draw.polygon(target, _scale(top, 0.55 if i == 0 else 0.4),
                            [(int(a), int(b)) for a, b in face])
    draw_diamond(target, iso, sx, sy, top, wx * 131 + wy, name, wx, wy)
    if name in ("farmland", "farmland2"):          # ISO.16 furrowed crop rows
        from ui import iso_tiles
        iso_tiles.draw_furrows(target, iso, sx, sy, wx, wy)


_SPRITES = {}


def _get_sprites(tile_size):
    """A cached SpriteLoader per tile size (for iso ground-item icons)."""
    if tile_size not in _SPRITES:
        from ui.sprite_loader import SpriteLoader
        _SPRITES[tile_size] = SpriteLoader(tile_size=tile_size)
    return _SPRITES[tile_size]


def _draw_surface(target, iso, data):
    """A translucent fire/oil/water pool as an iso diamond over the tile."""
    kind, sx, sy, clk = data
    from ui.animation import surface_fill
    col = surface_fill(kind, clk)
    pts = iso.diamond(sx, sy)
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    minx, miny = int(min(xs)), int(min(ys))
    w = int(max(xs) - minx) + 2
    h = int(max(ys) - miny) + 2
    if w <= 0 or h <= 0:
        return
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.polygon(s, col, [(int(x - minx), int(y - miny)) for x, y in pts])
    target.blit(s, (minx, miny))


def _draw_grounditem(target, data):
    """Dropped loot sitting on its tile (lifted to read on the ground)."""
    spr, sx, sy = data
    w, h = spr.get_size()
    target.blit(spr, (sx - w // 2, sy - int(h * 0.7)))


def _scatter_iso_sprite(name, ts):
    """A scatter prop for the iso view: BAKED 3D where we have it (boulder ->
    rock, gravestone -> the baked stone), else the flat billboard sprite."""
    if name in ("boulder", "rock"):
        from ui import iso_objects
        return iso_objects.rock_sprite(int(ts * 0.9))
    from ui import iso_furniture
    baked = iso_furniture.furniture_sprite(name, int(ts * 1.2))
    if baked is not None:                          # gravestone
        return baked
    from ui.scatter_sprites import scatter_sprite
    return scatter_sprite(name, int(ts * 0.85))


def _draw_scatter(target, data, tile_size):
    name, sx, sy = data
    spr = _scatter_iso_sprite(name, tile_size)
    if spr is None:
        return
    w, h = spr.get_size()
    target.blit(spr, (sx - w // 2, sy - int(h * 0.72)))


def _draw_pet_iso(target, data, tile_size):
    from ui.renderer_overlays import draw_pet
    pet, sx, sy = data
    ts = max(8, int(tile_size * 0.8))
    draw_pet(target, pet, sx - ts // 2, sy - int(ts * 0.68), ts)


def _draw_mount_iso(target, data, tile_size):
    from ui.renderer_overlays import draw_mount
    kind, sx, sy = data
    ts = max(10, int(tile_size * 1.1))
    draw_mount(target, kind, sx - ts // 2, sy - int(ts * 0.62), ts)


def _iso_to_screen(iso, origin, wmap, x, y):
    """World tile (float) → iso screen point, lifted by the tile's relief."""
    ix, iy = int(x), int(y)
    z = 0.0
    if 0 <= iy < wmap.height and 0 <= ix < wmap.width:
        z = _HEIGHT.get(_terrain_name(wmap.terrain[iy][ix]), 0.0)
    sx, sy = iso.world_to_screen(x, y, z, origin)
    return int(sx), int(sy)


def draw_combat_iso(target, engine, view_rect, iso, origin, wmap, tile_size):
    """Draw floating damage numbers / hit flashes / death particles in the iso
    view (P41.12) — on TOP, after the sky/interior light, like the top-down."""
    ce = getattr(engine, "combat_effects", None)
    if not ce:
        return
    try:
        # AGE the effects (bug-fix: the top-down renderer updates them each
        # frame; the iso path only drew them, so the red damage sprays never
        # expired — George). In iso mode dispatch() skips the top-down update,
        # so this is the single per-frame tick.
        ce.update(1.0 / 30.0)
        ce.draw_with(target, view_rect,
                     lambda x, y: _iso_to_screen(iso, origin, wmap, x, y),
                     tile_size)
    except Exception:
        pass


def _draw_iso_projectiles(target, engine, iso, origin, wmap, tile_size):
    from ui.body_renderer import draw_projectile
    try:
        active = list(engine.projectile_manager.active)
    except Exception:
        return
    for proj in active:
        ix, iy = int(proj.x), int(proj.y)
        z = 0.0
        if 0 <= iy < wmap.height and 0 <= ix < wmap.width:
            z = _HEIGHT.get(_terrain_name(wmap.terrain[iy][ix]), 0.0)
        sx, sy = iso.world_to_screen(proj.x, proj.y, z, origin)
        try:
            draw_projectile(target, proj.kind, int(sx), int(sy), tile_size)
        except Exception:
            pass


def _draw_iso_reticle(target, engine, iso, origin, wmap, tile_size,
                      x0, x1, y0, y1):
    tid = getattr(engine, "player_target_id", None)
    if not tid:
        return
    npc = engine.npc_manager.npcs.get(tid)
    if npc is None or not (hasattr(npc, "is_active") and npc.is_active()):
        return
    tx, ty = npc.position
    if not (x0 <= tx < x1 and y0 <= ty < y1):
        return
    z = _HEIGHT.get(_terrain_name(wmap.terrain[ty][tx]), 0.0)
    sx, sy = iso.world_to_screen(tx, ty, z, origin)
    pts = iso.diamond(sx, sy)
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    minx, maxx = int(min(xs)), int(max(xs))
    miny, maxy = int(min(ys)), int(max(ys))
    gold = (235, 195, 60)
    arm = max(4, tile_size // 4)
    for cx, cy, dx, dy in ((minx, miny, 1, 1), (maxx, miny, -1, 1),
                           (minx, maxy, 1, -1), (maxx, maxy, -1, -1)):
        pygame.draw.line(target, gold, (cx, cy), (cx + dx * arm, cy), 2)
        pygame.draw.line(target, gold, (cx, cy), (cx, cy + dy * arm), 2)


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




