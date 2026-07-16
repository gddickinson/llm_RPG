"""ISO.2 — textured iso ground DIAMONDS (reuse the top-down tile_variants).

The old iso ground was a flat 3-fleck diamond. This bakes the rich `tile_variants`
terrain texture (grass blades / water ripples / farmland furrows / rock / swamp
reeds — the same recipes the top-down world uses), squashes it to the 2:1
diamond footprint and CLIPS it to the diamond shape, so the iso ground reads as
real terrain, not flat colour. Cached per (name, variant, tw, th); a terrain
with no recipe returns None and the caller draws the flat diamond.
"""

import pygame

from ui import tile_variants

_CACHE = {}
_MASK = {}


def _base_name(name: str) -> str:
    """Strip a trailing variant digit ('grass2' → 'grass')."""
    return name.rstrip("0123456789") if name else name


def _diamond_mask(tw: int, th: int):
    m = _MASK.get((tw, th))
    if m is None:
        m = pygame.Surface((tw, th), pygame.SRCALPHA)
        pygame.draw.polygon(m, (255, 255, 255, 255),
                            [(tw // 2, 0), (tw, th // 2),
                             (tw // 2, th), (0, th // 2)])
        _MASK[(tw, th)] = m
    return m


def tile_diamond(name: str, wx: int, wy: int, tw: int, th: int):
    """A cached diamond-clipped textured tile top, or None (→ flat fallback)."""
    base = _base_name(name)
    var = tile_variants.variant_index(wx, wy, base, 6)
    key = (base, var, tw, th)
    if key in _CACHE:
        return _CACHE[key]
    tex = None
    try:
        tex = tile_variants.build_tile(base, var, max(8, max(tw, th)))
    except Exception:
        tex = None
    if tex is None:
        _CACHE[key] = None
        return None
    tex = pygame.transform.smoothscale(tex, (tw, th))
    surf = pygame.Surface((tw, th), pygame.SRCALPHA)
    surf.blit(tex, (0, 0))
    surf.blit(_diamond_mask(tw, th), (0, 0),
              special_flags=pygame.BLEND_RGBA_MULT)
    _CACHE[key] = surf
    return surf
