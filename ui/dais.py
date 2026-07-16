"""GX.2 — the teleport WAYSTONE as a raised, glowing DIAS.

George: "make the teleportation platforms larger (on a raised dias?) and easy
to see." A waystone was an invisible `Location` marker — no tile art at all.
Here each is drawn as a stepped stone DAIS (a low round ziggurat, ~1.5 tiles
across so it reads bigger than the ground) with an arcane RUNE-CIRCLE glowing on
top and an upward GLOW, so it's unmistakable from a distance. Pure geometry
(`dais_tiers`, `rune_circle`) + a thin pygame draw, headless-testable.
"""

import math

STONE_DK = (92, 92, 110)
STONE = (150, 150, 168)
STONE_HI = (192, 192, 210)
RUNE = (140, 230, 255)          # arcane cyan
GLOW = (90, 200, 255)


def dais_tiers(sx: int, sy: int, ts: int):
    """The stepped platform tiers as (x, y, w, h) ellipse rects — outer/lowest
    first, inner/highest last — centred on the tile, spilling ~1.5 tiles wide so
    the dais reads BIGGER than the ground."""
    cx, cy = sx + ts // 2, sy + ts // 2
    ds = int(ts * 1.5)
    n = 3
    tiers = []
    for i in range(n):
        w = ds - i * (ds // (n + 1))
        h = max(4, int(w * 0.5))
        lift = i * max(2, ts // 8)               # each tier a little higher
        tiers.append((cx - w // 2, cy - h // 2 - lift, w, h))
    return tiers


def rune_circle(sx: int, sy: int, ts: int):
    """(cx, cy, r) of the rune ring on the dais's top tier."""
    tx, ty, tw, th = dais_tiers(sx, sy, ts)[-1]
    return (tx + tw // 2, ty + th // 2, max(3, tw // 3))


def _radial_glow(target, cx, cy, r, color, alpha=110):
    import pygame
    for i in range(r, 0, -2):
        a = max(6, int(alpha * (1 - i / r) ** 1.3))
        s = pygame.Surface((i * 2, i * 2), pygame.SRCALPHA)
        pygame.draw.circle(s, (*color, a), (i, i), i)
        target.blit(s, (cx - i, cy - i))


def draw_dais(target, sx: int, sy: int, ts: int, phase: float = 0.0) -> None:
    """Draw the raised glowing waystone dais on the tile at (sx, sy). `phase`
    (0..1) gently pulses the rune glow."""
    import pygame
    tiers = dais_tiers(sx, sy, ts)
    cx = sx + ts // 2
    rcx, rcy, rr = rune_circle(sx, sy, ts)
    # 1) upward glow so it's visible from afar (a soft beam above the rune)
    beam_h = ts + tiers[0][3]
    beam = pygame.Surface((max(6, ts // 2), beam_h), pygame.SRCALPHA)
    for yy in range(beam_h):
        a = int(46 * (1 - yy / beam_h))
        pygame.draw.line(beam, (*GLOW, a), (0, yy), (beam.get_width(), yy))
    target.blit(beam, (cx - beam.get_width() // 2, rcy - beam_h),
                special_flags=pygame.BLEND_RGBA_ADD)
    # 2) stepped stone tiers (round), outer→inner, each brighter + higher
    for i, (ex, ey, w, h) in enumerate(tiers):
        shade = STONE_DK if i == 0 else (STONE if i == 1 else STONE_HI)
        pygame.draw.ellipse(target, STONE_DK, (ex, ey + 3, w, h))   # rim shadow
        pygame.draw.ellipse(target, shade, (ex, ey, w, h))
        pygame.draw.ellipse(target, STONE_HI, (ex, ey, w, h), 1)
    # 3) the arcane rune circle on top + its glow
    pulse = 0.7 + 0.3 * math.sin(phase * 2 * math.pi)
    _radial_glow(target, rcx, rcy, int(rr * 1.8), GLOW, int(80 * pulse))
    pygame.draw.ellipse(target, RUNE, (rcx - rr, rcy - rr // 2, 2 * rr, rr), 2)
    for k in range(6):                            # rune spokes
        ang = k * math.pi / 3 + phase
        ex = rcx + int(rr * math.cos(ang))
        ey = rcy + int((rr // 2) * math.sin(ang))
        pygame.draw.line(target, RUNE, (rcx, rcy), (ex, ey), 1)
    pygame.draw.circle(target, (235, 250, 255), (rcx, rcy), max(1, rr // 4))


def draw_all(target, engine, view_rect, cam_x, cam_y, ts) -> None:
    """Draw a dais at every waystone Location currently in view."""
    import pygame
    cols = view_rect.width // ts + 1
    rows = view_rect.height // ts + 1
    try:
        phase = (pygame.time.get_ticks() / 1600.0) % 1.0
    except Exception:
        phase = 0.0
    for loc in getattr(engine.world, "locations", []):
        if not (loc.properties or {}).get("waystone"):
            continue
        if not (cam_x <= loc.x < cam_x + cols and cam_y <= loc.y < cam_y + rows):
            continue
        sx = view_rect.x + (loc.x - cam_x) * ts
        sy = view_rect.y + (loc.y - cam_y) * ts
        draw_dais(target, sx, sy, ts, phase)
