"""#9 — realistic ANIMAL/MONSTER sprites baked from Quaternius GLB models (George:
"use the movieMaker Quaternius animals"). A GLB is loaded to per-primitive
(verts, tris, rgb) meshes — raster3d's OWN mesh format — normalised (feet on the
ground, centred, scaled to fill the frame), and baked once to an iso sprite via
`raster3d.bake` (cached). Graceful fallback: no pygltflib / no GLB for a species
-> None, and the caller keeps the procedural creature. GLB loader adapted from
movieMaker's mm/studio/char_meshes.
"""

import functools
import math
import os

try:
    import numpy as np
    import pygltflib as gl
    from ui import raster3d as r3
    GLB_OK = True
except Exception:                                    # pragma: no cover
    GLB_OK = False

_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "creatures")
_DT = {5120: "i1", 5121: "u1", 5122: "i2", 5123: "u2", 5125: "u4", 5126: "f4"}
_NC = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}

# game species -> Quaternius GLB basename (in data/creatures). Unmapped species
# (e.g. rabbit, pheasant, slimes, wisps) fall back to the procedural creature.
SPECIES_GLB = {
    "deer": "deer", "fox": "fox", "wolf": "wolf", "boar": "pig", "pig": "pig",
    "sheep": "sheep", "horse": "horse", "cow": "cow", "bull": "bull",
    "dog": "dog", "donkey": "donkey", "husky": "husky", "shark": "shark",
    "war_horse": "horse", "mule": "donkey",
}


def _acc(g, blob, i):
    a = g.accessors[i]
    bv = g.bufferViews[a.bufferView]
    off = (bv.byteOffset or 0) + (a.byteOffset or 0)
    arr = np.frombuffer(blob, np.dtype(_DT[a.componentType]),
                        a.count * _NC[a.type], off)
    return arr.reshape(a.count, _NC[a.type])


def _mat_color(g, pr):
    if pr.material is None:
        return (150, 150, 150)
    mat = g.materials[pr.material]
    bc = (getattr(mat.pbrMetallicRoughness, "baseColorFactor", None)
          if mat.pbrMetallicRoughness else None)
    if bc:                                   # lift the albedo — the iso Lambert
        # shading darkens the far side, so raw dark pelts read near-black
        return tuple(int(max(35, min(255, c * 255 * 1.3))) for c in bc[:3])
    return (155, 155, 155)


def _quat_matrix(q):
    x, y, z, w = q
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w), 0],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w), 0],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y), 0],
        [0, 0, 0, 1]], float)


def _local_matrix(node):
    """A glTF node's local TRS (or explicit matrix) as a 4x4."""
    if node.matrix:                       # glTF stores column-major
        return np.array(node.matrix, float).reshape(4, 4).T
    m = np.eye(4)
    if node.scale:
        m = np.diag([*node.scale, 1.0]) @ m
    if node.rotation:
        m = _quat_matrix(node.rotation) @ m
    if node.translation:
        t = np.eye(4)
        t[:3, 3] = node.translation
        m = t @ m
    return m


def _mesh_world_matrices(g):
    """(mesh_index -> world 4x4) for every node that references a mesh, walking
    the scene tree so each mesh's node transform (rotation/scale) is applied —
    Quaternius rigs park the body mesh under a -90°X, ×100 armature node."""
    scene = g.scenes[g.scene or 0]
    out = []

    def walk(ni, parent):
        node = g.nodes[ni]
        world = parent @ _local_matrix(node)
        if node.mesh is not None:
            out.append((node.mesh, world))
        for ci in (node.children or []):
            walk(ci, world)

    for ni in (scene.nodes or []):
        walk(ni, np.eye(4))
    return out


def load_meshes(glb_path):
    """A GLB -> [(verts Nx3, tris Mx3, rgb)] per primitive, each posed by its
    node's WORLD transform (keeps real colours)."""
    g = gl.GLTF2().load(glb_path)
    blob = g.binary_blob()
    out = []
    for mesh_idx, world in _mesh_world_matrices(g):
        rot = world[:3, :3]
        trans = world[:3, 3]
        for pr in g.meshes[mesh_idx].primitives:
            if pr.attributes.POSITION is None or pr.indices is None:
                continue
            pos = _acc(g, blob, pr.attributes.POSITION).astype(float)
            pos = pos @ rot.T + trans           # node world transform
            idx = _acc(g, blob, pr.indices).reshape(-1, 3).astype(np.int64)
            out.append((pos, idx, _mat_color(g, pr)))
    return out


def _normalise(meshes, angle_deg=0.0, target=1.5):
    """Feet on y=0, centred at the origin, scaled so the largest dimension is
    `target` units, then yaw-rotated `angle_deg` so the animal faces a heading."""
    allv = np.concatenate([v for v, _, _ in meshes])
    lo, hi = allv.min(axis=0), allv.max(axis=0)
    s = target / max((hi - lo).max(), 1e-6)
    cx, cz, min_y = (lo[0] + hi[0]) / 2, (lo[2] + hi[2]) / 2, lo[1]
    th = math.radians(angle_deg)
    c, sn = math.cos(th), math.sin(th)
    out = []
    for v, t, col in meshes:
        w = v.astype(float).copy()
        w[:, 0] = (w[:, 0] - cx) * s
        w[:, 1] = (w[:, 1] - min_y) * s
        w[:, 2] = (w[:, 2] - cz) * s
        x = w[:, 0] * c + w[:, 2] * sn
        z = -w[:, 0] * sn + w[:, 2] * c
        w[:, 0], w[:, 2] = x, z
        out.append((w, t, col))
    return out


_FACING = 45            # the canonical iso 3/4 heading — head to screen-LEFT,
#                         a clean front-3/4 standing view (flip for facing east)


@functools.lru_cache(maxsize=128)
def sprite(species, size, angle_deg=_FACING):
    """A baked iso sprite for `species` (or None → the procedural creature)."""
    if not GLB_OK:
        return None
    base = SPECIES_GLB.get((species or "").lower())
    if not base:
        return None
    path = os.path.join(_DIR, base + ".glb")
    if not os.path.exists(path):
        return None
    try:
        return r3.bake(_normalise(load_meshes(path), angle_deg), int(size))
    except Exception:
        return None


def species_of(char):
    """The GLB species key matching a creature's model hint / name / id, or None."""
    md = getattr(char, "metadata", None) or {}
    model = str(md.get("model", "")).lower()      # explicit override wins
    if model in SPECIES_GLB:
        return model
    name = " ".join(str(x) for x in (
        getattr(char, "name", "") or "", getattr(char, "id", "") or "",
        md.get("species", ""), md.get("template", ""))).lower()
    for key in SPECIES_GLB:
        if key in name:
            return key
    return None


def sprite_for_char(char, size, face_east=False):
    """A baked model sprite for `char`. The canonical bake faces screen-LEFT, so
    h-flip it when the creature is heading east. Returns None if unmodelled."""
    key = species_of(char)
    if key is None:
        return None
    spr = sprite(key, int(size))
    if spr is not None and face_east:
        try:
            import pygame
            return pygame.transform.flip(spr, True, False)
        except Exception:
            return spr
    return spr


def has_model(species) -> bool:
    base = SPECIES_GLB.get((species or "").lower())
    return bool(GLB_OK and base
               and os.path.exists(os.path.join(_DIR, base + ".glb")))
