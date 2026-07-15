"""P39.6b — overworld decorative scatter sprites (procedural, cached).

Small NATURE props for the overworld — a boulder, deadwood, a mushroom cluster,
ferns, reeds, flowers, a tree stump — drawn from pure geometry the way
`prop_sprites` does, plus a dispatch to `prop_sprites` for the shared bones /
gravestone. `scatter_sprite(name, ts)` returns a cached tile-sized RGBA sprite
(or None); BOTH renderers blit the same sprite so the scatter looks identical.
Props sit in the lower-centre of the tile so they read as standing on the
ground.
"""

import pygame

ROCK = (142, 138, 132)
ROCK_DK = (98, 94, 90)
ROCK_HI = (176, 172, 166)
BARK = (112, 84, 54)
BARK_DK = (74, 54, 34)
LEAF = (78, 128, 66)
LEAF_DK = (48, 92, 52)
CAP = (176, 66, 58)
CAP_HI = (212, 130, 120)
STALK = (222, 214, 190)
REED = (126, 156, 82)
REED_DK = (96, 128, 70)
PETALS = ((228, 200, 96), (206, 120, 172), (150, 170, 224))


def _boulder(s, ts):
    cx, by = ts // 2, int(ts * 0.82)
    w, h = int(ts * 0.5), int(ts * 0.36)
    pygame.draw.ellipse(s, ROCK_DK, (cx - w // 2, by - h, w, h))
    pygame.draw.ellipse(s, ROCK, (cx - w // 2, by - h - 2, w, h))
    pygame.draw.ellipse(s, ROCK_HI, (cx - w // 4, by - h, w // 3, h // 3))


def _deadwood(s, ts):
    cx, by = ts // 2, int(ts * 0.86)
    ty = int(ts * 0.28)
    pygame.draw.line(s, BARK_DK, (cx, by), (cx, ty), max(2, ts // 16))
    for dx, dy in ((-1, 0.5), (1, 0.42), (-1, 0.28)):
        mx = int(cx + dx * ts * 0.18)
        my = int(by - (by - ty) * dy)
        pygame.draw.line(s, BARK, (cx, my), (mx, my - ts // 8),
                         max(1, ts // 22))


def _mushroom(s, ts):
    for dx, sc in ((-0.16, 0.9), (0.14, 1.1), (0.02, 0.7)):
        cx = int(ts / 2 + dx * ts)
        by = int(ts * 0.84)
        r = max(2, int(ts * 0.11 * sc))
        pygame.draw.line(s, STALK, (cx, by), (cx, by - r), max(1, ts // 20))
        pygame.draw.ellipse(s, CAP, (cx - r, by - r - r // 2, 2 * r, r + 2))
        pygame.draw.ellipse(s, CAP_HI, (cx - r // 2, by - r - r // 2,
                                        r, r // 2 + 1))


def _reeds(s, ts):
    by = int(ts * 0.9)
    for i in range(5):
        cx = int(ts * (0.28 + i * 0.11))
        top = int(ts * (0.3 + (i % 2) * 0.12))
        col = REED if i % 2 else REED_DK
        pygame.draw.line(s, col, (cx, by), (cx, top), max(1, ts // 24))


def _fern(s, ts):
    cx, by = ts // 2, int(ts * 0.88)
    for ang in (-0.6, -0.2, 0.2, 0.6):
        ex = int(cx + ang * ts * 0.4)
        ey = int(by - ts * 0.42)
        pygame.draw.line(s, LEAF_DK, (cx, by), (ex, ey), max(1, ts // 22))
        pygame.draw.line(s, LEAF, (cx, by), (ex, ey + 2), max(1, ts // 30))


def _flowers(s, ts):
    by = int(ts * 0.88)
    for i, dx in enumerate((-0.14, 0.0, 0.15)):
        cx = int(ts / 2 + dx * ts)
        top = int(by - ts * (0.24 + 0.05 * i))
        pygame.draw.line(s, LEAF, (cx, by), (cx, top), max(1, ts // 26))
        col = PETALS[i % len(PETALS)]
        pygame.draw.circle(s, col, (cx, top), max(2, ts // 14))
        pygame.draw.circle(s, (250, 236, 150), (cx, top), max(1, ts // 30))


def _stump(s, ts):
    cx, by = ts // 2, int(ts * 0.82)
    w = int(ts * 0.34)
    h = int(ts * 0.16)
    pygame.draw.rect(s, BARK_DK, (cx - w // 2, by - h, w, h))
    pygame.draw.ellipse(s, BARK, (cx - w // 2, by - h - h // 2, w, h))
    pygame.draw.ellipse(s, (158, 122, 78),
                        (cx - w // 4, by - h - h // 3, w // 2, h // 2))


_NATURE = {
    "boulder": _boulder, "rock": _boulder,
    "deadwood": _deadwood, "deadtree": _deadwood, "snag": _deadwood,
    "mushroom": _mushroom, "toadstool": _mushroom,
    "reeds": _reeds, "reed": _reeds, "rushes": _reeds,
    "fern": _fern, "ferns": _fern,
    "flowers": _flowers, "flower": _flowers, "blossom": _flowers,
    "stump": _stump,
}

_CACHE = {}


def scatter_sprite(name, ts):
    """A cached, SUPERSAMPLED + ground-shadowed scatter sprite, or None if
    `name` isn't drawable. P40.3: built at ts·SSAA and smoothscaled (crisp
    curves) with a soft contact shadow so the prop reads as standing on the
    ground instead of floating; SSAA follows the "Smooth sprites" setting."""
    from ui import gfx, tile_variants, prop_sprites
    ss = tile_variants.SSAA if tile_variants.SSAA is not None \
        else gfx.ss_factor(3)
    key = (name, ts, ss)
    if key not in _CACHE:
        fn = _NATURE.get(name)
        if fn is not None:
            def _paint(S, _fn=fn):
                s = pygame.Surface((S, S), pygame.SRCALPHA)
                _fn(s, S)
                return s
            sprite = gfx.supersample(_paint, ts, ss)
            grounded = gfx.contact_shadow(ts, w_frac=0.5, alpha=95)
            grounded.blit(sprite, (0, 0))
            _CACHE[key] = grounded
        else:                                   # bones / gravestone / …
            _CACHE[key] = prop_sprites.render_prop(name, ts, ss=ss)
    return _CACHE[key]


def scatter_names():
    return list(_NATURE.keys())
