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
        color = DOOR_STATE_COLORS.get(state, (110, 75, 40))
        sx = view_rect.x + (dx - cam_x) * ts
        sy = view_rect.y + (dy - cam_y) * ts
        w, h = max(6, ts // 3), max(9, ts // 2)
        rect = (sx + (ts - w) // 2, sy + ts - h, w, h)
        pygame.draw.rect(target, color, rect, border_radius=2)
        pygame.draw.rect(target, (25, 18, 10), rect, 1, border_radius=2)
        if state == "locked":
            pygame.draw.circle(target, (210, 200, 90),
                               (rect[0] + w // 2, rect[1] + h // 2), 2)
        elif state == "open":
            pygame.draw.rect(target, (15, 12, 8),
                             (rect[0] + 2, rect[1] + 2, w - 4, h - 2))
        elif state == "broken":
            pygame.draw.line(target, (15, 12, 8), (rect[0], rect[1]),
                             (rect[0] + w, rect[1] + h), 2)
