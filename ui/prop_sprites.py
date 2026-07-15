"""P39.1 — decorative prop sprites (procedural, thin pygame draw).

The world comes alive with detail (George): a large library of recognizable
tile-sized props — pillars, braziers, torches, tapestries, sarcophagi, statues,
fountains, diases, gravestones, urns, cobwebs, candelabra, and more — each drawn
from pure geometry (no art assets), the way `roof_shapes`/`gate_shapes` do.

`draw_prop(surf, name, ts)` matches a prop by keyword and paints it onto `surf`,
returning True if it handled the name (else the caller falls back). Colours come
from a small material palette lifted from the reference projects' material DBs.
`sprite_loader.furniture()` dispatches here first, caching by name+size.
"""

import math

import pygame

# ---- material palette (from building-gen materials + autonomous_world) ----
STONE = (150, 146, 136)
STONE_DK = (96, 92, 84)
STONE_LT = (186, 182, 172)
MOSS = (96, 118, 80)
IRON = (92, 94, 102)
IRON_DK = (58, 60, 68)
WOOD = (140, 104, 66)
WOOD_DK = (96, 68, 42)
GOLD = (214, 176, 74)
BONE = (222, 214, 190)
BONE_DK = (168, 160, 138)
MARBLE = (224, 220, 210)
FIRE = (240, 140, 40)
FIRE_HI = (255, 224, 96)
FIRE_GLOW = (255, 170, 70)
CLOTH_RED = (150, 52, 52)
CLOTH_BLUE = (60, 84, 140)
CLOTH_GOLD = (176, 146, 70)
WATER = (90, 150, 200)
WATER_HI = (150, 200, 235)
COBWEB = (210, 210, 216)


def _shade(c, f):
    return tuple(max(0, min(255, int(v * f))) for v in c[:3])


def _flame(s, cx, by, ts):
    """A small licking flame with a bright core, apex above `by`."""
    h = max(4, ts // 4)
    w = max(3, ts // 6)
    pygame.draw.polygon(s, FIRE, [(cx - w // 2, by), (cx, by - h),
                                  (cx + w // 2, by)])
    pygame.draw.polygon(s, FIRE_HI, [(cx - w // 4, by), (cx, by - h * 2 // 3),
                                     (cx + w // 4, by)])


def _glow(s, cx, cy, r, color=FIRE_GLOW):
    """A soft radial glow (a few translucent rings) — a light source cue."""
    for i in range(r, 0, -2):
        a = max(6, int(70 * (1 - i / r)))
        g = pygame.Surface((i * 2, i * 2), pygame.SRCALPHA)
        pygame.draw.circle(g, (*color, a), (i, i), i)
        s.blit(g, (cx - i, cy - i))


# ---- props -----------------------------------------------------------------

def _pillar(s, ts):
    x0, x1 = ts // 3, 2 * ts // 3
    pygame.draw.rect(s, STONE, (x0, 3, x1 - x0, ts - 6))
    pygame.draw.rect(s, STONE_LT, (x0, 3, 3, ts - 6))          # lit edge
    pygame.draw.rect(s, STONE_DK, (x1 - 3, 3, 3, ts - 6))      # shade
    for y in (3, ts - 8):                                      # capital + base
        pygame.draw.rect(s, STONE_LT, (x0 - 3, y, x1 - x0 + 6, 5))
        pygame.draw.rect(s, STONE_DK, (x0 - 3, y + 4, x1 - x0 + 6, 1))


def _brazier(s, ts):
    _glow(s, ts // 2, ts // 3, ts // 2)
    pygame.draw.rect(s, IRON_DK, (ts // 2 - 2, ts // 2, 4, ts // 3))   # stem
    pygame.draw.polygon(s, IRON, [(ts // 3, ts // 2), (2 * ts // 3, ts // 2),
                                  (2 * ts // 3 - 3, ts * 2 // 3),
                                  (ts // 3 + 3, ts * 2 // 3)])          # bowl
    pygame.draw.line(s, IRON, (ts // 3, ts - 4), (ts // 2, ts * 2 // 3), 2)
    pygame.draw.line(s, IRON, (2 * ts // 3, ts - 4), (ts // 2, ts * 2 // 3), 2)
    _flame(s, ts // 2, ts // 2, ts)


def _torch(s, ts):
    _glow(s, ts // 2, ts // 3, ts // 3)
    pygame.draw.rect(s, IRON, (ts // 2 - 4, ts // 3, 8, 4))            # bracket
    pygame.draw.rect(s, WOOD_DK, (ts // 2 - 1, ts // 3, 3, ts // 3))   # haft
    _flame(s, ts // 2, ts // 3, ts)


def _tapestry(s, ts):
    pygame.draw.rect(s, WOOD_DK, (ts // 4 - 1, 3, ts // 2 + 2, 3))     # rod
    pygame.draw.rect(s, CLOTH_RED, (ts // 4, 5, ts // 2, ts - 12))
    pygame.draw.rect(s, CLOTH_GOLD, (ts // 4, 5, ts // 2, ts - 12), 2)
    pygame.draw.circle(s, GOLD, (ts // 2, ts // 2), max(3, ts // 8), 2)
    for fx in range(ts // 4, 3 * ts // 4, max(3, ts // 8)):           # fringe
        pygame.draw.line(s, CLOTH_GOLD, (fx, ts - 7), (fx, ts - 4), 1)


def _rug(s, ts):
    pygame.draw.ellipse(s, CLOTH_RED, (4, ts // 3, ts - 8, ts // 2))
    pygame.draw.ellipse(s, CLOTH_GOLD, (4, ts // 3, ts - 8, ts // 2), 2)
    pygame.draw.ellipse(s, CLOTH_BLUE, (ts // 3, ts // 2 - 2,
                                        ts // 3, ts // 4), 2)


def _sarcophagus(s, ts):
    pygame.draw.rect(s, STONE, (ts // 5, ts // 5, 3 * ts // 5, 3 * ts // 5),
                     border_radius=3)
    pygame.draw.rect(s, STONE_DK, (ts // 5, ts // 5, 3 * ts // 5,
                                   3 * ts // 5), 2, border_radius=3)
    pygame.draw.circle(s, STONE_LT, (ts // 2, ts // 3), max(3, ts // 10))
    pygame.draw.rect(s, STONE_LT, (ts // 2 - 2, ts // 3, 4, 2 * ts // 5))
    pygame.draw.line(s, STONE_DK, (ts // 3, ts * 2 // 5),
                     (2 * ts // 3, ts * 2 // 5), 1)                    # arms


def _tomb_slab(s, ts):
    pygame.draw.rect(s, STONE_DK, (ts // 5, ts // 4, 3 * ts // 5, ts // 2),
                     border_radius=2)
    pygame.draw.rect(s, STONE, (ts // 5 + 2, ts // 4 + 2,
                                3 * ts // 5 - 4, ts // 2 - 4))
    pygame.draw.line(s, STONE_DK, (ts // 3, ts // 3),
                     (2 * ts // 3, ts // 3), 1)


def _gravestone(s, ts):
    x0, w = ts // 3, ts // 3
    pygame.draw.rect(s, MOSS, (x0 - 2, ts * 3 // 4, w + 4, 4))         # ground
    pygame.draw.rect(s, STONE, (x0, ts // 4, w, ts // 2))
    pygame.draw.circle(s, STONE, (ts // 2, ts // 4), w // 2)           # round top
    pygame.draw.line(s, STONE_DK, (ts // 2, ts // 3), (ts // 2, ts // 2), 1)
    pygame.draw.line(s, STONE_DK, (ts // 2 - 3, ts * 2 // 5),
                     (ts // 2 + 3, ts * 2 // 5), 1)                    # cross


def _bones(s, ts):
    pygame.draw.circle(s, BONE, (ts // 2, ts * 3 // 5), max(3, ts // 8))
    pygame.draw.circle(s, BONE_DK, (ts // 2 - 2, ts * 3 // 5 - 1), 1)  # eye
    pygame.draw.circle(s, BONE_DK, (ts // 2 + 2, ts * 3 // 5 - 1), 1)
    for (a, b) in (((ts // 4, ts // 3), (ts // 2, ts * 2 // 5)),
                   ((2 * ts // 3, ts // 4), (ts // 2, ts // 2))):
        pygame.draw.line(s, BONE, a, b, 2)


def _cobweb(s, ts):
    for e in ((0, 0), (ts, 0)):
        cx = e[0]
        for r in range(ts // 4, ts, ts // 4):
            pygame.draw.arc(s, COBWEB,
                            (cx - r, e[1] - r, r * 2, r * 2),
                            *(( -math.pi / 2, 0) if cx == 0
                              else (math.pi, 3 * math.pi / 2)), 1)
        pygame.draw.line(s, COBWEB, e, (cx + (ts // 2 if cx == 0 else -ts // 2),
                                        ts // 2), 1)


def _urn(s, ts):
    cx = ts // 2
    pygame.draw.ellipse(s, WOOD, (ts // 3, ts // 3, ts // 3, ts * 2 // 5))
    pygame.draw.ellipse(s, WOOD_DK, (ts // 3, ts // 3, ts // 3, ts * 2 // 5), 1)
    pygame.draw.rect(s, WOOD_DK, (ts // 3 + 1, ts // 4, ts // 3 - 2, ts // 8))
    pygame.draw.arc(s, WOOD_DK, (ts // 4, ts // 3, ts // 6, ts // 5),
                    math.pi / 2, 3 * math.pi / 2, 2)                   # handle
    pygame.draw.arc(s, WOOD_DK, (7 * ts // 12, ts // 3, ts // 6, ts // 5),
                    -math.pi / 2, math.pi / 2, 2)


def _statue(s, ts):
    pygame.draw.rect(s, STONE_DK, (ts // 3, ts * 3 // 4, ts // 3, ts // 6))
    pygame.draw.rect(s, MARBLE, (ts // 3 + 3, ts // 3, ts // 3 - 6,
                                 ts * 5 // 12))                        # body
    pygame.draw.circle(s, MARBLE, (ts // 2, ts // 3), max(3, ts // 9))  # head
    pygame.draw.line(s, _shade(MARBLE, 0.8), (ts // 2, ts // 2),
                     (2 * ts // 5, ts * 2 // 5), 2)                    # arm


def _fountain(s, ts):
    pygame.draw.ellipse(s, STONE, (4, ts // 3, ts - 8, ts // 2))
    pygame.draw.ellipse(s, WATER, (8, ts // 3 + 3, ts - 16, ts // 2 - 6))
    pygame.draw.rect(s, STONE_LT, (ts // 2 - 2, ts // 4, 4, ts // 3))  # spout
    for dx in (-4, 0, 4):
        pygame.draw.line(s, WATER_HI, (ts // 2, ts // 4),
                         (ts // 2 + dx, ts // 2), 1)


def _dais(s, ts):
    pygame.draw.rect(s, STONE, (ts // 6, ts // 2, 2 * ts // 3, ts // 3))
    pygame.draw.rect(s, STONE_DK, (ts // 6, ts // 2, 2 * ts // 3, ts // 3), 1)
    pygame.draw.rect(s, CLOTH_RED, (ts // 4, ts // 4, ts // 2, ts // 3))  # seat
    pygame.draw.rect(s, GOLD, (ts // 4, ts // 4, ts // 2, 3))
    pygame.draw.rect(s, GOLD, (ts // 4, ts // 4, 3, ts // 3))


def _candelabra(s, ts):
    pygame.draw.rect(s, GOLD, (ts // 2 - 1, ts // 2, 3, ts // 3))      # stem
    pygame.draw.line(s, GOLD, (ts // 3, ts // 2), (2 * ts // 3, ts // 2), 2)
    for cx in (ts // 3, ts // 2, 2 * ts // 3):
        pygame.draw.rect(s, MARBLE, (cx - 1, ts // 2 - 5, 3, 5))       # candle
        _flame(s, cx, ts // 2 - 5, ts // 2)


def _chandelier(s, ts):
    pygame.draw.line(s, IRON, (ts // 2, 0), (ts // 2, ts // 4), 1)
    pygame.draw.ellipse(s, IRON, (ts // 4, ts // 4, ts // 2, ts // 5), 2)
    for cx in (ts // 3, ts // 2, 2 * ts // 3):
        _flame(s, cx, ts // 4 + 2, ts // 2)
    _glow(s, ts // 2, ts // 3, ts // 3, FIRE_GLOW)


def _cauldron(s, ts):
    _glow(s, ts // 2, 3 * ts // 4, ts // 3)
    for dx in (-5, 0, 5):
        _flame(s, ts // 2 + dx, 3 * ts // 4, ts // 3)                 # fire
    pygame.draw.ellipse(s, IRON_DK, (ts // 4, ts // 3, ts // 2, ts // 3))
    pygame.draw.arc(s, IRON, (ts // 4, ts // 4, ts // 2, ts // 3),
                    0, math.pi, 2)                                     # handle


def _weapon_rack(s, ts):
    pygame.draw.rect(s, WOOD_DK, (ts // 5, ts // 4, 3 * ts // 5, 3))   # top rail
    pygame.draw.rect(s, WOOD_DK, (ts // 5, 3 * ts // 4, 3 * ts // 5, 3))
    for i, cx in enumerate(range(ts // 4, 3 * ts // 4, max(5, ts // 6))):
        pygame.draw.line(s, IRON, (cx, ts // 4), (cx, 3 * ts // 4), 2)  # shaft
        if i % 2:
            pygame.draw.polygon(s, IRON, [(cx - 3, ts // 3), (cx + 3, ts // 3),
                                          (cx, ts // 4 - 3)])          # spear
        else:
            pygame.draw.line(s, IRON, (cx - 3, ts // 3),
                             (cx + 3, ts // 3), 2)                     # sword


def _crate(s, ts):
    pygame.draw.rect(s, WOOD, (ts // 4, ts // 4, ts // 2, ts // 2))
    pygame.draw.rect(s, WOOD_DK, (ts // 4, ts // 4, ts // 2, ts // 2), 2)
    pygame.draw.line(s, WOOD_DK, (ts // 4, ts // 4),
                     (3 * ts // 4, 3 * ts // 4), 1)
    pygame.draw.line(s, WOOD_DK, (3 * ts // 4, ts // 4),
                     (ts // 4, 3 * ts // 4), 1)


def _lectern(s, ts):
    pygame.draw.rect(s, WOOD_DK, (ts // 2 - 1, ts // 2, 3, ts // 3))   # post
    pygame.draw.polygon(s, WOOD, [(ts // 3, ts // 2), (2 * ts // 3, ts // 2),
                                  (2 * ts // 3 - 4, ts // 3),
                                  (ts // 3 + 4, ts // 3)])             # slope
    pygame.draw.rect(s, BONE, (ts // 3 + 4, ts * 2 // 5, ts // 3 - 8, ts // 8))


def _bench(s, ts):
    pygame.draw.rect(s, WOOD, (ts // 6, ts // 2, 2 * ts // 3, 5))      # seat
    pygame.draw.rect(s, WOOD_DK, (ts // 6, ts // 3, 2 * ts // 3, 4))   # back
    pygame.draw.rect(s, WOOD_DK, (ts // 6, ts // 2, 3, ts // 4))
    pygame.draw.rect(s, WOOD_DK, (5 * ts // 6 - 3, ts // 2, 3, ts // 4))


def _well(s, ts):
    pygame.draw.ellipse(s, STONE, (ts // 4, ts // 2, ts // 2, ts // 3))
    pygame.draw.ellipse(s, IRON_DK, (ts // 4 + 3, ts // 2 + 2,
                                     ts // 2 - 6, ts // 3 - 4))        # dark hole
    pygame.draw.line(s, WOOD_DK, (ts // 4, ts // 2), (ts // 3, ts // 4), 2)
    pygame.draw.line(s, WOOD_DK, (3 * ts // 4, ts // 2),
                     (2 * ts // 3, ts // 4), 2)
    pygame.draw.polygon(s, WOOD, [(ts // 3 - 3, ts // 4),
                                  (2 * ts // 3 + 3, ts // 4),
                                  (ts // 2, ts // 6)])                 # roof


def _mosaic(s, ts):
    cols = ((150, 60, 50), (60, 90, 140), (176, 146, 70), (96, 118, 80))
    n = max(3, ts // 10)
    for gy in range(4, ts - 4, n):
        for gx in range(4, ts - 4, n):
            pygame.draw.rect(s, cols[(gx + gy) // n % 4],
                             (gx, gy, n - 1, n - 1))


PROPS = {
    "pillar": _pillar, "column": _pillar,
    "brazier": _brazier,
    "torch": _torch, "sconce": _torch,
    "tapestry": _tapestry, "banner": _tapestry,
    "rug": _rug, "carpet": _rug,
    "sarcophagus": _sarcophagus, "coffin": _sarcophagus,
    "tomb": _tomb_slab, "slab": _tomb_slab,
    "gravestone": _gravestone, "grave": _gravestone, "headstone": _gravestone,
    "bone": _bones, "skull": _bones, "skeleton": _bones,
    "cobweb": _cobweb, "web": _cobweb,
    "urn": _urn, "amphora": _urn, "vase": _urn, "pot": _urn,
    "statue": _statue, "idol": _statue, "effigy": _statue,
    "fountain": _fountain,
    "dais": _dais, "throne": _dais,
    "candelabra": _candelabra, "candle": _candelabra,
    "chandelier": _chandelier,
    "cauldron": _cauldron,
    "weapon_rack": _weapon_rack, "rack": _weapon_rack, "armory": _weapon_rack,
    "crate": _crate,
    "lectern": _lectern, "bookstand": _lectern, "podium": _lectern,
    "bench": _bench,
    "well": _well,
    "mosaic": _mosaic,
}

# props that emit light (P39.4 will read this for interior glow)
LIT_PROPS = ("brazier", "torch", "sconce", "candelabra", "chandelier",
             "cauldron")


def draw_prop(surf, name: str, ts: int) -> bool:
    """Paint the prop matching `name` onto `surf`. Returns True if handled."""
    low = name.lower()
    for key, fn in PROPS.items():
        if key in low:
            fn(surf, ts)
            return True
    return False


def prop_names():
    """The distinct prop draw-functions, one representative name each."""
    seen, out = set(), []
    for key, fn in PROPS.items():
        if fn not in seen:
            seen.add(fn)
            out.append(key)
    return out


def emits_light(name: str) -> bool:
    low = name.lower()
    return any(k in low for k in LIT_PROPS)
