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


# ISO.16 crop palettes by growth mood, chosen per-tile so a field varies
_CROPS = [((92, 138, 60), (150, 116, 74)),      # young green
          ((104, 150, 58), (150, 116, 74)),     # growing
          ((170, 160, 74), (156, 120, 74)),     # ripening gold
          ((196, 178, 84), (160, 124, 78))]     # mature wheat


def draw_furrows(target, iso, sx, sy, wx, wy, rows=5):
    """ISO.16 draw FURROWED CROP rows on a farmland tile — parallel green/gold
    crop rows in dirt furrows, running along an iso axis and CONTINUOUS across
    neighbouring farm tiles, so a field reads as cultivated (George)."""
    hw, hh = iso.tw / 2.0, iso.th / 2.0
    crop, ridge = _CROPS[(wx * 7 + wy * 13) % len(_CROPS)]

    def S(fu, fv):
        return (sx + (fu - fv) * hw, sy - hh + (fu + fv) * hh)

    half = 0.32 / rows                            # crop-row half-thickness (v)
    for i in range(rows):
        v = (i + 0.5) / rows
        band = [S(0.02, v - half), S(0.98, v - half),
                S(0.98, v + half), S(0.02, v + half)]
        pygame.draw.polygon(target, crop,
                            [(int(a), int(b)) for a, b in band])
        # a lit ridge along the row's up-slope edge → a hint of 3D furrow
        a, b = S(0.02, v - half), S(0.98, v - half)
        pygame.draw.line(target, ridge, (int(a[0]), int(a[1])),
                         (int(b[0]), int(b[1])), 1)
