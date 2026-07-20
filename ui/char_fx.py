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
    draw_status(surface, char, sx, sy, tile_size, clock)


# H5: status conditions shown ON the body — a blessing haloes gold, poison bubbles
# green, a curse smokes dark violet. Read from the character's active effects.
_STATUS_FX = (("blessed", (255, 224, 130), "aura"),
              ("poisoned", (96, 205, 96), "wisps"),
              ("cursed", (156, 74, 190), "aura"))


def draw_status(surface, char, sx, sy, ts, t):
    """Overlay a soft cue for each active magical condition (H5)."""
    if not PYGAME_OK:
        return
    try:
        from characters.status_effects import has_effect
    except Exception:
        return
    for name, col, kind in _STATUS_FX:
        try:
            if not has_effect(char, name):
                continue
        except Exception:
            continue
        (_aura if kind == "aura" else _wisps)(surface, sx, sy, ts, t, col)


def _aura(surface, sx, sy, ts, t, col):
    """A soft pulsing glow RING that hugs the body (blessing / curse) — an outline,
    not a filled blob, so it frames the figure instead of washing it out."""
    pulse = 0.55 + 0.45 * (0.5 + 0.5 * math.sin(t * 3.0))
    d = int(ts * 2.0)
    g = pygame.Surface((d, d), pygame.SRCALPHA)
    c = d // 2
    ew, eh = int(d * 0.26), int(d * 0.46)              # a tall, body-shaped ring
    for i, a in enumerate((26, 46, 70)):               # concentric fading edges
        pygame.draw.ellipse(g, (col[0], col[1], col[2], int(a * pulse)),
                            (c - ew - 2 + i * 2, c - eh - 2 + i * 2,
                             (ew + 2 - i * 2) * 2, (eh + 2 - i * 2) * 2), 2)
    surface.blit(g, (int(sx + ts / 2 - c), int(sy + ts * 0.30 - c)))


def _wisps(surface, sx, sy, ts, t, col):
    """Rising bubbles/wisps (poison)."""
    cx = sx + ts / 2.0
    for i in range(5):
        p = (t * 1.1 + i / 5.0) % 1.0
        wx = cx + math.sin((t * 2 + i) * 1.7) * ts * 0.26
        wy = sy + ts * 0.9 - p * ts * 0.85
        r = max(1, int(ts * 0.06 * (1.0 - p * 0.5)))
        a = int(150 * (1.0 - p))
        g = pygame.Surface((r * 2 + 2, r * 2 + 2), pygame.SRCALPHA)
        pygame.draw.circle(g, (col[0], col[1], col[2], a), (r + 1, r + 1), r)
        surface.blit(g, (int(wx - r), int(wy - r)))


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
