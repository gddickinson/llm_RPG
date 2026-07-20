"""ISO.1 — richer baked 3D BUILDING meshes for the isometric world.

The old iso building was one flat box + a gable/parapet lump. This builds a
believable little structure from the SAME style data the top-down renderer uses
(`data/building_styles.json` via `renderer_buildings.style_for` +
`building_variety`): storey-driven HEIGHT (a tower towers over a cottage), a
real roof SHAPE (gable ridge / hip pyramid / flat parapet), recessed WINDOW
boxes per storey on the two camera-facing walls, a DOOR, and a CHIMNEY — in the
building's own WALL + COVERING materials, varied per-building so clones differ.

Pure mesh construction (lists of `raster3d` boxes/prisms); `iso_objects` bakes
+ caches the result. Cache key includes the (covering, wall) variant, so the
distinct looks are bounded (~a handful per kind), not one per map tile.
"""

import numpy as np

from ui import raster3d as r3
from ui import roof_shapes as rs
from ui.renderer_buildings import storeys_for, style_for

_STOREY_H = 0.6
_WALL_W = 1.06                       # footprint half-ish (unit-ish object)
_WIN = (44, 42, 54)
_DOOR = (58, 40, 28)
_CHIMNEY = (86, 74, 66)
_TALL = ("tower", "keep", "watchtower", "wall_tower", "mill")


def pyramid(cx, cy, cz, w, h, d, color):
    """A hip roof — four triangular slopes rising to a central apex."""
    x0, x1 = cx - w / 2, cx + w / 2
    z0, z1 = cz - d / 2, cz + d / 2
    v = np.array([[x0, cy, z0], [x1, cy, z0], [x1, cy, z1], [x0, cy, z1],
                  [cx, cy + h, cz]], float)
    t = np.array([[0, 1, 4], [1, 2, 4], [2, 3, 4], [3, 0, 4]])
    return v, t, color


def _windows(w, d, storeys):
    """Recessed dark window boxes on the +z (front) and +x (right) walls — the
    two the fixed iso camera sees — a pair per storey."""
    out = []
    for s in range(storeys):
        wy = s * _STOREY_H + _STOREY_H * 0.34
        for wx in (-w * 0.26, w * 0.26):             # front wall (z+)
            out.append(r3.box(wx, wy, d / 2, w * 0.2, _STOREY_H * 0.4,
                              0.06, _WIN))
        out.append(r3.box(w / 2, wy, 0, 0.06, _STOREY_H * 0.4,        # right (x+)
                          d * 0.24, _WIN))
    return out


def building_mesh(kind: str, covering: str = None, wall: str = None):
    """A rich building mesh for `kind` in the given (covering, wall) materials
    (defaulting to the kind's own style)."""
    style = style_for(kind)
    wall_c = rs.wall_color(wall or style.get("wall", "timber"))
    cover_c = rs.covering_color(covering or style.get("covering", "clay"))
    storeys = max(1, storeys_for(kind))
    tall = kind in _TALL
    w = d = _WALL_W * (0.9 if tall else 1.0)
    h = storeys * _STOREY_H
    meshes = [r3.box(0, 0, 0, w, h, d, wall_c)]
    meshes += _windows(w, d, storeys)
    # a door on the front wall
    meshes.append(r3.box(0, 0, d / 2, w * 0.28, _STOREY_H * 0.72, 0.06, _DOOR))
    # the roof by shape
    shape = style.get("roof", "gable")
    if shape == "flat" or tall:
        meshes.append(r3.box(0, h, 0, w + 0.12, 0.14, d + 0.12,
                             rs._scale(cover_c, 1.05)))          # parapet
        if tall:                                                # a crown block
            meshes.append(r3.box(0, h + 0.14, 0, w * 0.5, 0.12, d * 0.5,
                                 rs._scale(cover_c, 0.9)))
    elif shape == "hip":
        meshes.append(pyramid(0, h, 0, w + 0.16, 0.62, d + 0.16, cover_c))
    else:                                                       # gable ridge
        meshes.append(r3.roof(0, h, 0, w + 0.16, 0.56, d + 0.08, cover_c))
    # a chimney for a hearthed building
    if style.get("chimneys") and shape != "flat" and not tall:
        meshes.append(r3.box(w * 0.3, h + 0.06, d * 0.14, 0.15, 0.4, 0.15,
                             _CHIMNEY))
        meshes.append(r3.box(w * 0.3, h + 0.44, d * 0.14, 0.19, 0.06, 0.19,
                             rs._scale(_CHIMNEY, 1.2)))
    return meshes
