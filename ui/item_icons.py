"""Richer item ICONS (replaces the flat 3-shape procedural glyph).

`sprite_loader.item` drew almost everything as one brown box. This draws
a recognizable, TYPE-aware glyph for each item — a sword, a bow, a flask,
a ring, a tome, an ore chunk… — with a RARITY frame/glow, supersampled
for crisp edges (the P40 beauty pass). Pure procedural, cached.

`icon(item, size)` reads an item's type + rarity; `icon_by_name(name,
size, rarity)` infers the archetype from keywords alone (for the
ground/shop path, which only has a name). Both return a cached SRCALPHA
Surface of the given size.
"""

import pygame

from ui import gfx

OUTLINE = (28, 24, 30)
METAL = (198, 205, 218)
METAL_DK = (118, 124, 142)
GOLD = (224, 186, 92)
WOOD = (146, 99, 58)
WOOD_DK = (92, 62, 38)
LEATHER = (156, 116, 74)
GLASS = (150, 202, 222)
CLOTH = (92, 112, 176)
PAPER = (228, 216, 188)
STONE = (146, 146, 158)
LEAF = (96, 172, 96)
RED = (202, 82, 74)
BLUE = (86, 134, 224)

RARITY = {"common": (170, 170, 175), "uncommon": (96, 200, 112),
          "rare": (92, 150, 232), "epic": (182, 112, 222),
          "legendary": (232, 172, 74)}

# keyword → archetype (checked in order; first hit wins). A keyword < 4
# chars only matches a WHOLE WORD (so "hat" ⊄ "whatsit"); compound one-word
# names are listed explicitly.
_KEYWORDS = [
    ("crossbow", "bow"), ("longbow", "bow"), ("shortbow", "bow"),
    ("warbow", "bow"), ("bow", "bow"), ("sling", "bow"),
    ("dagger", "dagger"), ("dirk", "dagger"), ("knife", "dagger"),
    ("battleaxe", "axe"), ("greataxe", "axe"), ("handaxe", "axe"),
    ("hatchet", "axe"), ("axe", "axe"),
    ("warhammer", "mace"), ("maul", "mace"), ("hammer", "mace"),
    ("mace", "mace"), ("club", "mace"), ("flail", "mace"),
    ("halberd", "spear"), ("glaive", "spear"), ("trident", "spear"),
    ("spear", "spear"), ("pike", "spear"), ("lance", "spear"),
    ("staff", "staff"), ("rod", "staff"), ("scepter", "wand"),
    ("wand", "wand"),
    ("scimitar", "sword"), ("rapier", "sword"), ("falchion", "sword"),
    ("sabre", "sword"), ("sword", "sword"), ("blade", "sword"),
    ("glaive", "sword"), ("edge", "sword"), ("brand", "sword"),
    ("robe", "robe"), ("cloak", "robe"), ("gown", "robe"),
    ("vestment", "robe"),
    ("buckler", "shield"), ("aegis", "shield"), ("shield", "shield"),
    ("greaves", "boots"), ("sandal", "boots"), ("boot", "boots"),
    ("circlet", "helmet"), ("crown", "helmet"), ("helmet", "helmet"),
    ("helm", "helmet"), ("cap", "helmet"), ("hat", "helmet"),
    ("necklace", "amulet"), ("pendant", "amulet"), ("talisman", "amulet"),
    ("medallion", "amulet"), ("amulet", "amulet"),
    ("ring", "ring"), ("band", "ring"),
    ("potion", "flask"), ("elixir", "flask"), ("draught", "flask"),
    ("tonic", "flask"), ("brew", "flask"), ("ale", "flask"),
    ("mead", "flask"), ("wine", "flask"), ("oil", "flask"),
    ("bandage", "bandage"), ("poultice", "bandage"), ("salve", "bandage"),
    ("remedy", "bandage"),
    ("ration", "food"), ("bread", "food"), ("meat", "food"),
    ("fish", "food"), ("cheese", "food"), ("apple", "food"),
    ("jerky", "food"), ("stew", "food"), ("food", "food"),
    ("scroll", "scroll"),
    ("spellbook", "book"), ("grimoire", "book"), ("tome", "book"),
    ("manual", "book"), ("book", "book"), ("codex", "book"),
    ("quiver", "arrow"), ("arrow", "arrow"), ("bolt", "arrow"),
    ("ingot", "ore"), ("nugget", "ore"), ("ore", "ore"),
    ("mushroom", "herb"), ("berries", "herb"), ("flower", "herb"),
    ("herb", "herb"), ("leaf", "herb"), ("root", "herb"),
    ("plank", "log"), ("timber", "log"), ("log", "log"), ("wood", "log"),
    ("diamond", "gem"), ("ruby", "gem"), ("emerald", "gem"),
    ("sapphire", "gem"), ("crystal", "gem"), ("jewel", "gem"),
    ("gem", "gem"), ("shard", "gem"), ("dust", "gem"),
    ("coin", "coins"), ("gold", "coins"),
    ("key", "key"),
    ("rucksack", "bag"), ("sack", "bag"), ("pouch", "pouch"),
    ("bag", "bag"), ("pack", "bag"),
    ("orb", "orb"), ("relic", "orb"), ("idol", "orb"), ("charm", "orb"),
]

_TYPE_FALLBACK = {
    "weapon": "sword", "armor": "breastplate", "shield": "shield",
    "boots": "boots", "ring": "ring", "amulet": "amulet",
    "consumable": "flask", "scroll": "scroll", "book": "book",
    "ammo": "arrow", "ingredient": "pouch", "currency": "coins",
    "key": "key", "misc": "crate", "quest": "crate",
}

_cache = {}


def _classify(itype, name):
    import re
    n = (name or "").lower()
    words = set(re.findall(r"[a-z]+", n))
    for kw, arch in _KEYWORDS:
        if len(kw) >= 4:
            if kw in n:                          # long enough to be unambiguous
                return arch
        elif kw in words:                        # short kw → whole-word only
            return arch
    return _TYPE_FALLBACK.get(itype, "crate")


# ---- primitive helpers (draw at supersampled scale S) -----------------

def _c(surf, col, cx, cy, r):
    pygame.draw.circle(surf, col, (int(cx), int(cy)), int(r))


def _line(surf, col, a, b, w):
    pygame.draw.line(surf, col, a, b, max(1, int(w)))


def _poly(surf, col, pts, outline=True):
    pygame.draw.polygon(surf, col, pts)
    if outline:
        pygame.draw.polygon(surf, OUTLINE, pts, max(1, int(len(pts) and 1)))


# ---- archetype glyphs (S = full supersampled size) --------------------

def _sword(s, S):
    m = S / 2
    _line(s, METAL, (m, S * 0.14), (m, S * 0.66), S * 0.09)
    _line(s, (240, 244, 250), (m - S * 0.015, S * 0.16),
          (m - S * 0.015, S * 0.62), S * 0.02)
    _line(s, GOLD, (m - S * 0.16, S * 0.66), (m + S * 0.16, S * 0.66),
          S * 0.06)                                            # crossguard
    _line(s, WOOD, (m, S * 0.66), (m, S * 0.84), S * 0.07)     # grip
    _c(s, GOLD, m, S * 0.86, S * 0.05)                         # pommel


def _dagger(s, S):
    m = S / 2
    _line(s, METAL, (m, S * 0.24), (m, S * 0.60), S * 0.08)
    _line(s, GOLD, (m - S * 0.11, S * 0.60), (m + S * 0.11, S * 0.60),
          S * 0.05)
    _line(s, LEATHER, (m, S * 0.60), (m, S * 0.78), S * 0.06)


def _axe(s, S):
    _line(s, WOOD, (S * 0.40, S * 0.16), (S * 0.56, S * 0.86), S * 0.07)
    _poly(s, METAL, [(S * 0.42, S * 0.20), (S * 0.80, S * 0.24),
                     (S * 0.74, S * 0.46), (S * 0.44, S * 0.42)])


def _mace(s, S):
    m = S / 2
    _line(s, WOOD, (m, S * 0.40), (m, S * 0.86), S * 0.07)
    _c(s, METAL_DK, m, S * 0.30, S * 0.18)
    for a in range(0, 360, 45):
        import math
        dx, dy = math.cos(math.radians(a)), math.sin(math.radians(a))
        _c(s, METAL, m + dx * S * 0.18, S * 0.30 + dy * S * 0.18, S * 0.045)


def _bow(s, S):
    rect = pygame.Rect(int(S * 0.30), int(S * 0.12), int(S * 0.42),
                       int(S * 0.76))
    pygame.draw.arc(s, WOOD, rect, -1.4, 1.4, max(2, int(S * 0.06)))
    _line(s, (235, 230, 210), (S * 0.44, S * 0.14), (S * 0.44, S * 0.86),
          S * 0.015)                                           # string


def _spear(s, S):
    m = S / 2
    _line(s, WOOD, (m, S * 0.28), (m, S * 0.88), S * 0.05)
    _poly(s, METAL, [(m, S * 0.10), (m - S * 0.08, S * 0.30),
                     (m + S * 0.08, S * 0.30)])


def _staff(s, S):
    m = S / 2
    _line(s, WOOD, (m, S * 0.24), (m, S * 0.90), S * 0.06)
    _c(s, BLUE, m, S * 0.20, S * 0.11)
    _c(s, (180, 220, 255), m - S * 0.03, S * 0.17, S * 0.035)


def _wand(s, S):
    _line(s, WOOD_DK, (S * 0.34, S * 0.74), (S * 0.64, S * 0.34), S * 0.05)
    _c(s, (255, 235, 150), S * 0.66, S * 0.30, S * 0.08)
    _c(s, (255, 255, 220), S * 0.66, S * 0.30, S * 0.035)


def _breastplate(s, S):
    _poly(s, METAL, [(S * 0.30, S * 0.26), (S * 0.70, S * 0.26),
                     (S * 0.74, S * 0.48), (S * 0.50, S * 0.80),
                     (S * 0.26, S * 0.48)])
    _line(s, METAL_DK, (S * 0.50, S * 0.30), (S * 0.50, S * 0.70), S * 0.02)


def _robe(s, S):
    _poly(s, CLOTH, [(S * 0.40, S * 0.22), (S * 0.60, S * 0.22),
                     (S * 0.74, S * 0.82), (S * 0.26, S * 0.82)])
    _line(s, (60, 78, 130), (S * 0.50, S * 0.24), (S * 0.50, S * 0.80),
          S * 0.03)


def _shield(s, S):
    _poly(s, METAL, [(S * 0.28, S * 0.20), (S * 0.72, S * 0.20),
                     (S * 0.72, S * 0.56), (S * 0.50, S * 0.86),
                     (S * 0.28, S * 0.56)])
    _c(s, GOLD, S * 0.50, S * 0.46, S * 0.08)


def _boots(s, S):
    pygame.draw.rect(s, LEATHER, (int(S * 0.36), int(S * 0.24),
                                  int(S * 0.16), int(S * 0.44)))
    _poly(s, LEATHER, [(S * 0.36, S * 0.60), (S * 0.36, S * 0.74),
                       (S * 0.68, S * 0.74), (S * 0.66, S * 0.60)])


def _helmet(s, S):
    m = S / 2
    pygame.draw.arc(s, METAL, pygame.Rect(int(S * 0.28), int(S * 0.24),
                    int(S * 0.44), int(S * 0.52)), 0, 3.15, max(2, int(S * 0.14)))
    _line(s, METAL_DK, (m, S * 0.28), (m, S * 0.52), S * 0.02)


def _ring(s, S):
    m = S / 2
    pygame.draw.circle(s, GOLD, (int(m), int(S * 0.58)), int(S * 0.20),
                       max(2, int(S * 0.06)))
    _c(s, RED, m, S * 0.36, S * 0.08)


def _amulet(s, S):
    m = S / 2
    pygame.draw.arc(s, GOLD, pygame.Rect(int(S * 0.30), int(S * 0.18),
                    int(S * 0.40), int(S * 0.40)), 3.3, 6.1, max(2, int(S * 0.03)))
    _c(s, BLUE, m, S * 0.60, S * 0.12)
    _c(s, (200, 230, 255), m - S * 0.03, S * 0.56, S * 0.04)


def _flask(s, S):
    m = S / 2
    _line(s, (210, 210, 210), (m, S * 0.16), (m, S * 0.30), S * 0.05)
    pygame.draw.circle(s, GLASS, (int(m), int(S * 0.58)), int(S * 0.24))
    pygame.draw.circle(s, RED, (int(m), int(S * 0.62)), int(S * 0.19))
    _c(s, (255, 255, 255), m - S * 0.07, S * 0.50, S * 0.04)   # highlight
    _line(s, WOOD_DK, (m, S * 0.14), (m, S * 0.20), S * 0.06)  # cork


def _food(s, S):
    _poly(s, (190, 140, 80), [(S * 0.28, S * 0.60), (S * 0.50, S * 0.30),
                              (S * 0.72, S * 0.60), (S * 0.62, S * 0.74),
                              (S * 0.38, S * 0.74)])
    _c(s, (150, 100, 55), S * 0.50, S * 0.60, S * 0.05)


def _bandage(s, S):
    pygame.draw.rect(s, PAPER, (int(S * 0.28), int(S * 0.40),
                                int(S * 0.44), int(S * 0.20)))
    _line(s, (200, 190, 165), (S * 0.36, S * 0.34), (S * 0.30, S * 0.66),
          S * 0.03)


def _scroll(s, S):
    pygame.draw.rect(s, PAPER, (int(S * 0.30), int(S * 0.24),
                                int(S * 0.40), int(S * 0.52)))
    _c(s, (210, 200, 175), S * 0.30, S * 0.50, S * 0.06)
    _c(s, (210, 200, 175), S * 0.70, S * 0.50, S * 0.06)
    for i in range(3):
        y = S * (0.36 + 0.10 * i)
        _line(s, (150, 130, 100), (S * 0.38, y), (S * 0.62, y), S * 0.02)


def _book(s, S):
    pygame.draw.rect(s, (140, 60, 60), (int(S * 0.28), int(S * 0.26),
                                        int(S * 0.44), int(S * 0.48)))
    pygame.draw.rect(s, PAPER, (int(S * 0.32), int(S * 0.30),
                                int(S * 0.36), int(S * 0.40)))
    _line(s, GOLD, (S * 0.50, S * 0.30), (S * 0.50, S * 0.70), S * 0.03)


def _arrow(s, S):
    _line(s, WOOD, (S * 0.24, S * 0.76), (S * 0.72, S * 0.28), S * 0.03)
    _poly(s, METAL, [(S * 0.72, S * 0.28), (S * 0.62, S * 0.34),
                     (S * 0.66, S * 0.42)])
    _line(s, (220, 220, 210), (S * 0.24, S * 0.76), (S * 0.32, S * 0.70),
          S * 0.03)


def _ore(s, S):
    _poly(s, STONE, [(S * 0.30, S * 0.56), (S * 0.42, S * 0.36),
                     (S * 0.64, S * 0.34), (S * 0.72, S * 0.56),
                     (S * 0.56, S * 0.72), (S * 0.34, S * 0.68)])
    _c(s, (190, 170, 120), S * 0.48, S * 0.52, S * 0.05)
    _c(s, (190, 170, 120), S * 0.60, S * 0.46, S * 0.03)


def _herb(s, S):
    m = S / 2
    _line(s, (80, 120, 60), (m, S * 0.80), (m, S * 0.44), S * 0.03)
    _c(s, LEAF, m - S * 0.10, S * 0.40, S * 0.10)
    _c(s, LEAF, m + S * 0.10, S * 0.40, S * 0.10)
    _c(s, LEAF, m, S * 0.28, S * 0.10)


def _log(s, S):
    pygame.draw.rect(s, WOOD, (int(S * 0.26), int(S * 0.42),
                              int(S * 0.48), int(S * 0.20)))
    _c(s, WOOD_DK, S * 0.26, S * 0.52, S * 0.10)
    _c(s, (170, 130, 90), S * 0.26, S * 0.52, S * 0.05)


def _gem(s, S):
    m = S / 2
    _poly(s, (120, 210, 235), [(m, S * 0.24), (S * 0.70, S * 0.46),
                               (m, S * 0.76), (S * 0.30, S * 0.46)])
    _line(s, (255, 255, 255), (m, S * 0.24), (S * 0.30, S * 0.46), S * 0.02)
    _line(s, (255, 255, 255), (m, S * 0.24), (m, S * 0.76), S * 0.015)


def _coins(s, S):
    _c(s, GOLD, S * 0.40, S * 0.58, S * 0.16)
    _c(s, GOLD, S * 0.58, S * 0.50, S * 0.16)
    _c(s, (255, 235, 150), S * 0.58, S * 0.50, S * 0.10)


def _key(s, S):
    m = S / 2
    pygame.draw.circle(s, GOLD, (int(m), int(S * 0.34)), int(S * 0.12),
                       max(2, int(S * 0.05)))
    _line(s, GOLD, (m, S * 0.44), (m, S * 0.80), S * 0.05)
    _line(s, GOLD, (m, S * 0.72), (m + S * 0.12, S * 0.72), S * 0.05)


def _bag(s, S):
    _poly(s, LEATHER, [(S * 0.34, S * 0.36), (S * 0.66, S * 0.36),
                       (S * 0.74, S * 0.80), (S * 0.26, S * 0.80)])
    _line(s, WOOD_DK, (S * 0.38, S * 0.40), (S * 0.62, S * 0.40), S * 0.03)


def _pouch(s, S):
    _c(s, LEATHER, S * 0.50, S * 0.58, S * 0.22)
    _line(s, WOOD_DK, (S * 0.36, S * 0.42), (S * 0.64, S * 0.42), S * 0.04)


def _orb(s, S):
    m = S / 2
    _c(s, (110, 90, 190), m, S * 0.52, S * 0.24)
    _c(s, (170, 150, 240), m - S * 0.06, S * 0.44, S * 0.09)
    _c(s, (240, 235, 255), m - S * 0.09, S * 0.40, S * 0.035)


def _crate(s, S):
    pygame.draw.rect(s, WOOD, (int(S * 0.28), int(S * 0.30),
                              int(S * 0.44), int(S * 0.44)))
    pygame.draw.rect(s, WOOD_DK, (int(S * 0.28), int(S * 0.30),
                    int(S * 0.44), int(S * 0.44)), max(1, int(S * 0.03)))
    _line(s, WOOD_DK, (S * 0.28, S * 0.30), (S * 0.72, S * 0.74), S * 0.02)


_DRAW = {
    "sword": _sword, "dagger": _dagger, "axe": _axe, "mace": _mace,
    "bow": _bow, "spear": _spear, "staff": _staff, "wand": _wand,
    "breastplate": _breastplate, "robe": _robe, "shield": _shield,
    "boots": _boots, "helmet": _helmet, "ring": _ring, "amulet": _amulet,
    "flask": _flask, "food": _food, "bandage": _bandage, "scroll": _scroll,
    "book": _book, "arrow": _arrow, "ore": _ore, "herb": _herb,
    "log": _log, "gem": _gem, "coins": _coins, "key": _key, "bag": _bag,
    "pouch": _pouch, "orb": _orb, "crate": _crate,
}


def _render(arch, rarity, size):
    ss = gfx.ss_factor(2)

    def build(S):
        surf = pygame.Surface((S, S), pygame.SRCALPHA)
        col = RARITY.get(rarity, RARITY["common"])
        if rarity in ("epic", "legendary"):      # a soft glow behind
            glow = pygame.Surface((S, S), pygame.SRCALPHA)
            _c(glow, col + (70,), S / 2, S / 2, S * 0.40)
            surf.blit(glow, (0, 0))
        _DRAW.get(arch, _crate)(surf, S)
        if rarity != "common":                   # a rarity frame
            pygame.draw.rect(surf, col, (1, 1, S - 2, S - 2),
                             max(1, int(S * 0.03)),
                             border_radius=int(S * 0.12))
        return surf

    return gfx.supersample(build, size, ss)


def icon(item, size):
    itype = getattr(getattr(item, "item_type", None), "value", "misc")
    rarity = getattr(getattr(item, "rarity", None), "value", "common")
    arch = _classify(itype, getattr(item, "name", ""))
    return _cached(arch, rarity, size)


def icon_by_name(name, size, rarity="common"):
    arch = _classify("misc", name)
    return _cached(arch, rarity, size)


def _cached(arch, rarity, size):
    key = (arch, rarity, size)
    spr = _cache.get(key)
    if spr is None:
        try:
            spr = _render(arch, rarity, size)
        except Exception:
            spr = pygame.Surface((size, size), pygame.SRCALPHA)
        _cache[key] = spr
    return spr
