"""P41.8 — baked 3D FURNITURE sprites for the isometric interiors.

The iso zone renderer used to billboard flat prop sprites onto the floor; this
bakes the common furniture pieces as small 3D MESHES (boxes, a roof cap, a
glowing flame) rasterised ONCE via `raster3d.bake` into cached iso sprites — so
a sarcophagus, pillar, altar, table, chest or brazier reads as a real solid
object in the 2:1 view at zero per-frame 3D cost. Matched by keyword like
`prop_sprites`; an unmapped name returns None and the caller falls back to the
2D prop billboard.
"""

from ui import raster3d as r3

_CACHE = {}

# a small material palette (raster3d Lambert-shades each face from these)
STONE = (150, 150, 158)
STONE_D = (96, 98, 108)
MARBLE = (206, 200, 186)
WOOD = (142, 98, 56)
WOOD_D = (98, 66, 38)
IRON = (92, 94, 104)
GOLD = (208, 176, 92)
FIRE = (255, 150, 60)
CLOTH = (168, 78, 78)
BONE = (212, 206, 180)


def _box(cx, y, cz, w, h, d, c):
    return r3.box(cx, y, cz, w, h, d, c)


# --- per-piece mesh builders (centred on the tile, base on the floor) -------

def _pillar():
    return [_box(0, 0, 0, 0.34, 0.14, 0.34, STONE_D),      # base
            _box(0, 0.14, 0, 0.24, 1.35, 0.24, STONE),     # shaft
            _box(0, 1.49, 0, 0.36, 0.16, 0.36, STONE_D)]   # capital


def _sarcophagus():
    return [_box(0, 0, 0, 0.56, 0.34, 0.86, STONE),
            _box(0, 0.34, 0, 0.62, 0.14, 0.92, MARBLE)]    # lid


def _altar():
    return [_box(0, 0, 0, 0.72, 0.16, 0.5, STONE_D),
            _box(0, 0.16, 0, 0.5, 0.34, 0.34, MARBLE),
            _box(0, 0.5, 0, 0.56, 0.08, 0.4, GOLD)]        # top slab


def _table():
    legs = [_box(sx, 0, sz, 0.08, 0.34, 0.08, WOOD_D)
            for sx in (-0.26, 0.26) for sz in (-0.18, 0.18)]
    return legs + [_box(0, 0.34, 0, 0.72, 0.1, 0.52, WOOD)]


def _chest():
    return [_box(0, 0, 0, 0.5, 0.32, 0.36, WOOD),
            _box(0, 0.32, 0, 0.53, 0.14, 0.39, WOOD_D)]    # lid


def _barrel():
    return [_box(0, 0, 0, 0.34, 0.5, 0.34, WOOD_D),
            _box(0, 0.12, 0, 0.4, 0.12, 0.4, WOOD),        # belly hoops
            _box(0, 0.34, 0, 0.4, 0.1, 0.4, WOOD)]


def _crate():
    return [_box(0, 0, 0, 0.46, 0.46, 0.46, WOOD)]


def _brazier():
    return [_box(0, 0, 0, 0.16, 0.44, 0.16, IRON),         # stand
            _box(0, 0.44, 0, 0.42, 0.16, 0.42, IRON),      # bowl
            _box(0, 0.58, 0, 0.3, 0.24, 0.3, FIRE)]        # flame (glows)


def _bench():
    return [_box(sx, 0, 0, 0.1, 0.22, 0.28, WOOD_D)
            for sx in (-0.28, 0.28)] + \
           [_box(0, 0.22, 0, 0.74, 0.1, 0.3, WOOD)]


def _anvil():
    return [_box(0, 0, 0, 0.32, 0.24, 0.2, IRON),
            _box(0, 0.24, 0, 0.46, 0.12, 0.18, STONE_D)]


def _bed():
    return [_box(0, 0, 0, 0.82, 0.2, 0.52, WOOD_D),
            _box(0, 0.2, 0, 0.76, 0.14, 0.46, CLOTH),
            _box(-0.3, 0.34, 0, 0.16, 0.1, 0.4, MARBLE)]   # pillow


def _gravestone():
    return [_box(0, 0, 0, 0.42, 0.62, 0.14, STONE),
            _box(0, 0.62, 0, 0.42, 0.14, 0.14, STONE_D)]


def _shelf():
    return [_box(0, 0, 0, 0.5, 1.1, 0.22, WOOD_D),
            _box(0, 0.38, 0, 0.52, 0.06, 0.24, WOOD),
            _box(0, 0.74, 0, 0.52, 0.06, 0.24, WOOD)]


def _statue():
    return [_box(0, 0, 0, 0.44, 0.18, 0.44, STONE_D),
            _box(0, 0.18, 0, 0.26, 0.9, 0.22, MARBLE),
            _box(0, 1.08, 0, 0.2, 0.2, 0.2, MARBLE)]       # head


def _throne():
    return [_box(0, 0, 0, 0.6, 0.34, 0.5, STONE_D),        # seat block
            _box(0, 0.34, -0.16, 0.56, 0.7, 0.16, GOLD)]   # tall back


def _well():
    return [_box(0, 0, 0, 0.6, 0.36, 0.6, STONE),
            _box(0, 0.36, 0, 0.66, 0.08, 0.66, STONE_D)]


def _hearth():
    return [_box(0, 0, 0, 0.6, 0.5, 0.34, STONE),
            _box(0, 0.14, 0.14, 0.34, 0.24, 0.14, FIRE)]   # embers (glow)


def _urn():
    return [_box(0, 0, 0, 0.26, 0.14, 0.26, BONE),
            _box(0, 0.14, 0, 0.34, 0.24, 0.34, BONE),
            _box(0, 0.38, 0, 0.22, 0.12, 0.22, BONE)]


# keyword → builder (checked in order; first substring hit wins)
_BUILDERS = [
    ("sarcophag", _sarcophagus), ("tomb", _sarcophagus), ("coffin", _sarcophagus),
    ("pillar", _pillar), ("column", _pillar),
    ("altar", _altar), ("shrine", _altar),
    ("throne", _throne), ("dais", _throne),
    ("brazier", _brazier), ("sconce", _brazier),
    ("hearth", _hearth), ("forge", _hearth), ("furnace", _hearth),
    ("anvil", _anvil),
    ("table", _table), ("lectern", _shelf), ("desk", _table),
    ("chest", _chest), ("coffer", _chest),
    ("barrel", _barrel), ("cask", _barrel),
    ("crate", _crate), ("box", _crate),
    ("bench", _bench), ("pew", _bench), ("seat", _bench),
    ("bed", _bed), ("cot", _bed),
    ("gravestone", _gravestone), ("grave", _gravestone), ("headstone", _gravestone),
    ("statue", _statue), ("idol", _statue),
    ("shelf", _shelf), ("bookcase", _shelf), ("rack", _shelf),
    ("well", _well), ("fountain", _well),
    ("urn", _urn), ("vase", _urn),
]


def furniture_mesh(name):
    low = (name or "").lower()
    for kw, builder in _BUILDERS:
        if kw in low:
            return builder()
    return None


def furniture_sprite(name, size):
    """A cached baked 3D furniture sprite, or None if `name` isn't mapped
    (the caller then falls back to the flat prop billboard)."""
    low = (name or "").lower()
    for kw, builder in _BUILDERS:
        if kw in low:
            key = (kw, size)
            if key not in _CACHE:
                _CACHE[key] = r3.bake(builder(), size=size)
            return _CACHE[key]
    return None
