"""Character draw WRAPPERS split from `body_renderer` (to hold the 500-line
line): the SSAA beauty pass, the glimpsed-through-a-window glaze, and the
in-flight projectile sprite. All delegate to `body_renderer.draw_body`.
"""

import math

try:
    import pygame
    PYGAME_OK = True
except Exception:                                    # pragma: no cover
    PYGAME_OK = False

try:
    import numpy as np
    NUMPY_OK = True
except Exception:                                    # pragma: no cover
    NUMPY_OK = False

from ui import body_renderer as _br

# H6 dynamic lighting — a directional MULTIPLY gradient relights the character by
# the world's light: the side facing a light source stays bright/warm, the far
# side sinks to shadow. Built as a MULTIPLY (never ADD) so it can't halo the
# transparent pixels around the sprite; masked implicitly by the sprite's alpha.
_GRAD_CACHE = {}


def _relight_gradient(w, h, qdir, lit, shadow):
    """A cached linear gradient (w×h): `lit` colour toward the light direction
    `qdir` (0-15, in π/8 steps), `shadow` colour away. Multiplied onto the sprite."""
    key = (w, h, qdir, lit, shadow)
    g = _GRAD_CACHE.get(key)
    if g is not None:
        return g
    ang = qdir * (math.pi / 8.0)
    dx, dy = math.cos(ang), math.sin(ang)
    xs = np.linspace(-1.0, 1.0, w)[:, None]          # (w,1)
    ys = np.linspace(-1.0, 1.0, h)[None, :]          # (1,h)
    t = np.clip((xs * dx + ys * dy + 1.0) * 0.5, 0.0, 1.0)   # 0 shadow → 1 lit
    lit_a = np.array(lit, float)
    sh_a = np.array(shadow, float)
    rgb = sh_a[None, None, :] * (1 - t[..., None]) + lit_a[None, None, :] * t[..., None]
    g = pygame.surfarray.make_surface(rgb.astype(np.uint8))
    _GRAD_CACHE[key] = g
    return g


def apply_relight(scratch, light):
    """Relight `scratch` (the isolated character sprite) by a world light:
    `light` = (dx, dy, lit_rgb, shadow_rgb). BLEND_MULT keeps the sprite's alpha,
    so only drawn pixels are touched."""
    if not (PYGAME_OK and NUMPY_OK and light):
        return
    dx, dy, lit, shadow = light
    qdir = int(round(math.atan2(dy, dx) / (math.pi / 8.0))) % 16
    w, h = scratch.get_size()
    grad = _relight_gradient(w, h, qdir, tuple(lit), tuple(shadow))
    scratch.blit(grad, (0, 0), special_flags=pygame.BLEND_MULT)


def draw_body_crisp(surface, char, sx: int, sy: int, tile_size: int,
                    is_player: bool = False) -> None:
    """P34.7 beauty pass: render the character onto a `SSAA_SCALE`× oversampled
    scratch surface and `smoothscale` it down, so the curvy limbs read smooth and
    anti-aliased instead of jagged pixel steps. Falls back to a direct draw when
    oversampling is off. The logical grid + all animation are unchanged."""
    n = _br.SSAA_SCALE
    if not PYGAME_OK or n <= 1:
        return _br.draw_body(surface, char, sx, sy, tile_size, is_player)
    pad_x = tile_size                     # room for arms / weapon to the sides
    pad_up = tile_size * 2                 # the body overflows ~1.5 tiles upward
    w, h = tile_size + pad_x * 2, tile_size + pad_up
    scratch = pygame.Surface((w * n, h * n), pygame.SRCALPHA)
    _br.draw_body(scratch, char, pad_x * n, pad_up * n, tile_size * n, is_player)
    light = (getattr(char, "metadata", None) or {}).get("_relight")
    if light:                                 # H6 relight by the world's light
        apply_relight(scratch, light)
    small = pygame.transform.smoothscale(scratch, (w, h))
    surface.blit(small, (int(sx - pad_x), int(sy - pad_up)))


def draw_glimpsed(surface, char, sx: int, sy: int, tile_size: int,
                  is_player: bool = False) -> None:
    """Draw a character SEEN THROUGH A WINDOW (P14.2) — dimmed and behind a
    faint pane — so an NPC glimpsed inside a building reads as indoors rather
    than standing on top of the wall. Reuses `draw_body` on a taller scratch
    surface (the body overflows the tile), then glazes it."""
    if not PYGAME_OK:
        return
    pad = tile_size                          # room for the overflowing body
    glass = pygame.Surface((tile_size, tile_size + pad), pygame.SRCALPHA)
    _br.draw_body(glass, char, 0, pad, tile_size)
    glass.fill((255, 255, 255, 135), special_flags=pygame.BLEND_RGBA_MULT)
    surface.blit(glass, (sx, sy - pad))
    pane = pygame.Surface((tile_size, tile_size), pygame.SRCALPHA)
    pygame.draw.rect(pane, (140, 170, 205, 70), pane.get_rect(),
                     max(1, tile_size // 16))
    surface.blit(pane, (sx, sy))


def draw_projectile(surface, kind: str, sx: int, sy: int,
                    tile_size: int) -> None:
    """Draw an in-flight projectile sprite (called by the map renderer)."""
    if not PYGAME_OK:
        return
    cx = sx + tile_size // 2
    cy = sy + tile_size // 2
    if kind == "arrow":
        pygame.draw.line(surface, (200, 170, 110),
                         (cx - 4, cy), (cx + 4, cy), 2)
        pygame.draw.polygon(surface, (220, 220, 230),
                            [(cx + 4, cy - 2), (cx + 7, cy), (cx + 4, cy + 2)])
    elif kind == "bolt":
        pygame.draw.line(surface, (160, 160, 170),
                         (cx - 3, cy), (cx + 5, cy), 3)
    elif kind == "stone":
        pygame.draw.circle(surface, (140, 130, 120), (cx, cy), 3)
    elif kind == "spell":
        pygame.draw.circle(surface, (200, 160, 255), (cx, cy), 4)
        pygame.draw.circle(surface, (255, 220, 255), (cx, cy), 2)
    else:
        pygame.draw.circle(surface, (240, 240, 200), (cx, cy), 3)
