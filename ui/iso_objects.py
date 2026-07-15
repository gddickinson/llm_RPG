"""P41.4 — baked 3D object sprites for the isometric world.

Each building / tree is a small 3D MESH (box walls + a roof, coloured from the
P33.3 building styles) rasterised ONCE via `raster3d.bake` into a cached iso
sprite the scene blits like any 2D image — real 3D-looking objects at zero
per-frame 3D cost. Cached by (kind, size); the scene (`iso_render`) places them
at their tile and depth-sorts them with the terrain.
"""

from ui import raster3d as r3
from ui import roof_shapes as rs
from ui.renderer_buildings import style_for

_CACHE = {}
_TALL = ("tower", "keep", "watchtower", "wall_tower", "mill")


def _building_mesh(kind: str):
    style = style_for(kind)
    wall = rs.wall_color(style.get("wall", "timber"))
    cover = rs.covering_color(style.get("covering", "clay"))
    tall = kind in _TALL
    h = 1.7 if tall else 0.95
    w = d = 1.05
    meshes = [r3.box(0, 0, 0, w, h, d, wall)]
    if style.get("roof") == "flat" or tall:
        # a parapet / crenellated cap
        meshes.append(r3.box(0, h, 0, w + 0.12, 0.16, d + 0.12,
                             rs._scale(cover, 1.0)))
    else:
        meshes.append(r3.roof(0, h, 0, w + 0.18, 0.55, d + 0.06, cover))
    return meshes


def building_sprite(kind: str, size: int):
    """A cached baked 3D sprite for a building of `kind` at `size` px."""
    key = ("bld", kind, size)
    if key not in _CACHE:
        _CACHE[key] = r3.bake(_building_mesh(kind), size=size)
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
