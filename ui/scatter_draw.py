"""P39.6b — the TOP-DOWN overworld scatter draw pass (thin).

Blits a decorative scatter prop on each explored overworld tile the pure
`overworld_scatter.prop_at` selects. Called from `renderer.render` after the
2.5D building pass and before characters, so props sit on the ground and the
cast draws over them. The isometric renderer runs the same placement inside its
own depth-sorted pass.
"""


def draw_scatter(target, engine, view_rect, cam_x, cam_y, ts) -> None:
    from ui.overworld_scatter import prop_at
    from ui.scatter_sprites import scatter_sprite
    from ui.renderer import _TERRAIN_TO_SPRITE
    try:
        from engine.discovery import is_explored
    except Exception:
        is_explored = None

    wmap = engine.world.map
    cols = view_rect.width // ts
    rows = view_rect.height // ts
    for sy in range(rows):
        for sx in range(cols):
            wx, wy = cam_x + sx, cam_y + sy
            if not (0 <= wx < wmap.width and 0 <= wy < wmap.height):
                continue
            if is_explored is not None and not is_explored(engine, wx, wy):
                continue
            name = _TERRAIN_TO_SPRITE.get(wmap.terrain[wy][wx], "grass")
            prop = prop_at(wx, wy, name)
            if not prop:
                continue
            spr = scatter_sprite(prop, ts)
            if spr is None:
                continue
            target.blit(spr, (view_rect.x + sx * ts, view_rect.y + sy * ts))
