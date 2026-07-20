"""P41.4 — baked 3D object sprites for the isometric world.

Each building / tree is a small 3D MESH (box walls + a roof, coloured from the
P33.3 building styles) rasterised ONCE via `raster3d.bake` into a cached iso
sprite the scene blits like any 2D image — real 3D-looking objects at zero
per-frame 3D cost. Cached by (kind, size); the scene (`iso_render`) places them
at their tile and depth-sorts them with the terrain.
"""

from ui import raster3d as r3
from ui import iso_buildings

_CACHE = {}


def building_sprite(kind: str, size: int, covering: str = None,
                    wall: str = None):
    """A cached baked 3D sprite for a building of `kind` at `size` px, in the
    given (covering, wall) MATERIALS (ISO.1 per-building variety). Keyed by the
    variant so distinct looks are bounded, not one per tile."""
    key = ("bld", kind, covering, wall, size)
    if key not in _CACHE:
        _CACHE[key] = r3.bake(
            iso_buildings.building_mesh(kind, covering, wall), size=size)
    return _CACHE[key]


def tree_sprite(size: int):
    """A cached baked 3D tree (trunk + foliage)."""
    key = ("tree", size)
    if key not in _CACHE:
        trunk = r3.box(0, 0, 0, 0.16, 0.5, 0.16, (96, 68, 42))
        foliage = r3.box(0, 0.42, 0, 0.72, 0.7, 0.72, (44, 96, 52))
        top = r3.box(0, 0.95, 0, 0.42, 0.4, 0.42, (56, 116, 64))
        _CACHE[key] = r3.bake([trunk, foliage, top], size=size)
    return _CACHE[key]


def rock_sprite(size: int):
    """A cached baked 3D boulder (for mountains scatter)."""
    key = ("rock", size)
    if key not in _CACHE:
        _CACHE[key] = r3.bake(
            [r3.box(0, 0, 0, 0.7, 0.55, 0.6, (120, 112, 106))], size=size)
    return _CACHE[key]
