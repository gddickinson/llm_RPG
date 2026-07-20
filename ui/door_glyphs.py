"""P9A.3b — visible door glyphs on enterable buildings (split from renderer.py
to hold the 500-line line). A door is drawn on each enterable building's south
face, coloured by its lock state (open / closed / locked / broken)."""

import pygame

DOOR_STATE_COLORS = {
    "open": (110, 75, 40),
    "closed": (130, 95, 55),
    "locked": (95, 70, 50),
    "broken": (60, 45, 30),
}


def draw_door_glyphs(target, engine, view_rect, cam_x, cam_y, cols, rows,
                     ts) -> None:
    for loc in getattr(engine.world, "locations", []):
        if loc.name not in getattr(engine, "interiors", {}):
            continue
        dx = loc.x + loc.width // 2
        dy = loc.y + loc.height - 1
        if not (cam_x <= dx < cam_x + cols and cam_y <= dy < cam_y + rows):
            continue
        try:
            door = engine.door_manager.door(loc.name)
            state = engine.door_manager._effective_state(door)
        except Exception:
            state = "open"
        sx = view_rect.x + (dx - cam_x) * ts
        sy = view_rect.y + (dy - cam_y) * ts
        # BLD.4/5: per-kind shopfront (awning/sign/glow) then the entrance door
        kind = loc.get_property("type", "") if hasattr(loc, "get_property") \
            else ""
        from ui import facade
        facade.draw_shopfront(target, sx, sy, ts, kind)
        facade.draw_door(target, sx, sy, ts, kind, state)
