"""P34.19 physical-effect overlays — fire & water.

Drawn over a character by `body_renderer` when the engine flags a condition on
`metadata`: `_fx_fire` (rising flames + an ember tint) while burning, `_fx_wet`
(a bluish sheen + running drips) while soaked. Deterministic (driven by the anim
clock, no rng) so it renders headless; the thrown-through-air tumble and the
on-fire flail are pose CLIPS (see `char_clips_more`), this is just the particles.
"""

import math

try:
    import pygame
    PYGAME_OK = True
except ImportError:                                    # pragma: no cover
    PYGAME_OK = False


def draw_effects(surface, char, sx, sy, tile_size, clock):
    if not PYGAME_OK:
        return
    md = getattr(char, "metadata", None) or {}
    if md.get("_fx_fire", 0) > 0:
        _fire(surface, sx, sy, tile_size, clock)
    if md.get("_fx_wet", 0) > 0:
        _wet(surface, sx, sy, tile_size, clock)


def _fire(surface, sx, sy, ts, t):
    cx = sx + ts / 2.0
    base = sy + ts * 0.85
    for i in range(8):
        p = (t * 1.6 + i / 8.0) % 1.0                  # 0 at the base → 1 at the tip
        fx = cx + math.sin((t * 4 + i) * 1.3) * ts * 0.22 * (1.0 - p)
        fy = base - p * ts * 1.15                      # rises past the head
        r = max(1, int(ts * 0.14 * (1.0 - p)))
        a = int(210 * (1.0 - p))
        col = (255, int(80 + 130 * (1.0 - p)), 30)
        g = pygame.Surface((r * 2 + 2, r * 2 + 2), pygame.SRCALPHA)
        pygame.draw.circle(g, (col[0], col[1], col[2], a), (r + 1, r + 1), r)
        surface.blit(g, (int(fx - r), int(fy - r)))


def _wet(surface, sx, sy, ts, t):
    sheen = pygame.Surface((ts, ts), pygame.SRCALPHA)
    sheen.fill((90, 150, 210, 45))                     # a cool wet film
    surface.blit(sheen, (sx, sy))
    cx = sx + ts / 2.0
    for i in range(4):                                 # drips running off
        p = (t * 2.2 + i / 4.0) % 1.0
        dx = cx + (i - 1.5) * ts * 0.16
        dy = sy + ts * 0.35 + p * ts * 0.6
        pygame.draw.circle(surface, (150, 195, 230),
                           (int(dx), int(dy)), max(1, ts // 22))
