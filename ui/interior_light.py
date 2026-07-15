"""P39.4 — interior light sources & mood (thin pygame draw over a zone).

Makes warm-vs-dank READ: a dank crypt is dark except for warm POOLS of light
around its braziers/torches (and a small light the hero carries), with pale DUST
drifting in the still air; a lived-in home is barely darkened and glows warm.

`draw(...)` lays a theme darkness over the room, SUBTRACTS a radial hole around
every lit prop (`prop_sprites.emits_light`) + the player, ADDS a warm glow at the
fire sources for colour, then drifts dust motes for dank/deserted themes. Glow /
hole surfaces are cached by (radius, colour); dust animates off a frame counter.
"""

import math

import pygame

_CACHE = {}
_frame = 0
DARK_RGB = (6, 8, 12)


def _hole(radius: int):
    """A radial ALPHA gradient (opaque centre → clear edge) to SUBTRACT from the
    darkness layer, opening a pool of visibility."""
    key = ("hole", radius)
    if key not in _CACHE:
        s = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
        for r in range(radius, 0, -1):
            a = int(255 * (1 - r / radius))
            pygame.draw.circle(s, (0, 0, 0, a), (radius, radius), r)
        _CACHE[key] = s
    return _CACHE[key]


def _glow(radius: int, color):
    """A radial warm colour (bright centre → black edge) to ADD for warmth."""
    key = ("glow", radius, tuple(color))
    if key not in _CACHE:
        s = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
        for r in range(radius, 0, -1):
            f = (1 - r / radius) ** 2
            c = tuple(int(v * f) for v in color)
            pygame.draw.circle(s, c, (radius, radius), r)
        _CACHE[key] = s
    return _CACHE[key]


def _sources(zone, ts):
    """Lit-prop positions (zone coords) → glow radius."""
    from ui import prop_sprites
    out = []
    for f in getattr(zone, "furniture", []):
        if prop_sprites.emits_light(f.get("name", "")):
            out.append((f.get("x"), f.get("y")))
    return out


def _dust(target, view_rect, n, frame):
    w, h = view_rect.width, view_rect.height
    if w <= 0 or h <= 0:
        return
    for i in range(int(n)):
        bx = (i * 97 + 7) % w
        by = (i * 61 + frame) % h                    # slow fall
        wob = int(5 * math.sin(frame * 0.05 + i))
        x = view_rect.x + (bx + wob) % w
        y = view_rect.y + by
        a = 30 + (i * 17) % 45
        target.fill((198, 196, 186, a), (x, y, 2, 2),
                    special_flags=pygame.BLEND_RGBA_ADD)


def draw(target, zone, view_rect, cam_x, cam_y, ts, theme,
         player_pos=None) -> None:
    """Cast interior light + mood over the zone view."""
    global _frame
    _frame = (_frame + 1) % 100000
    light = (theme or {}).get("light") or {}
    dark_a = int(light.get("dark", 0))
    glow_col = tuple(light.get("glow", (255, 170, 70)))
    prad = int(ts * 2.4)
    plyr_rad = int(ts * 3.0)

    srcs = _sources(zone, ts)

    if dark_a > 0:
        dark = pygame.Surface((view_rect.width, view_rect.height),
                              pygame.SRCALPHA)
        dark.fill((*DARK_RGB, dark_a))
        for (fx, fy) in srcs:
            sx = (fx - cam_x) * ts + ts // 2
            sy = (fy - cam_y) * ts + ts // 2
            dark.blit(_hole(prad), (sx - prad, sy - prad),
                      special_flags=pygame.BLEND_RGBA_SUB)
        if player_pos is not None:
            sx = (player_pos[0] - cam_x) * ts + ts // 2
            sy = (player_pos[1] - cam_y) * ts + ts // 2
            dark.blit(_hole(plyr_rad), (sx - plyr_rad, sy - plyr_rad),
                      special_flags=pygame.BLEND_RGBA_SUB)
        target.blit(dark, (view_rect.x, view_rect.y))

    grad = int(ts * 2.0)
    for (fx, fy) in srcs:                             # warm colour pools
        sx = view_rect.x + (fx - cam_x) * ts + ts // 2
        sy = view_rect.y + (fy - cam_y) * ts + ts // 2
        target.blit(_glow(grad, glow_col), (sx - grad, sy - grad),
                    special_flags=pygame.BLEND_RGB_ADD)

    if light.get("dust"):
        _dust(target, view_rect, light["dust"], _frame)
