"""#9b — ANIMATED creatures from the Quaternius GLB skeletal clips.

The GLB models ship rigged with Walk / Idle / Gallop / Attack / Eating / Death
clips (+ a skin). This SKINS the mesh (joint world matrices × inverse-bind ×
per-vertex weights) at N phases of a clip and bakes each phase to a cached iso
sprite — so a beast WALKS (legs striding), idles (breathing), attacks and dies
instead of standing as one frozen bind pose (George: "they aren't animated").

Baking is lazy + cached per (species, clip, frame, size), so a visible beast is
a dict lookup + blit once its cycle is warm; the first sighting bakes a clip's
frames as the phase advances. Graceful fallback to the static bind-pose sprite
(`creature_glb.sprite_for_char`) when a rig / clip / pygltflib is unavailable.
"""

import functools
import math

from ui import creature_glb as cg

try:
    import numpy as np
    from ui import raster3d as r3
    _OK = cg.GLB_OK
except Exception:                                    # pragma: no cover
    _OK = False

NFRAMES = 8                     # baked phases per clip cycle
_ATTACK_DUR = 0.32

# a game action → the preferred clip names; the first present in the species wins
_CLIP_PREF = {
    "walk": ["Walk"],
    "run": ["Gallop", "Walk"],
    "idle": ["Idle", "Idle_2"],
    "attack": ["Attack", "Attack_Headbutt", "Attack_Kick"],
    "hurt": ["Idle_HitReact_Left", "Idle_HitReact_Right"],
    "dead": ["Death"],
    "eat": ["Eating"],
}


def _trs(t, r, s):
    m = np.diag([s[0], s[1], s[2], 1.0])
    m = cg._quat_matrix(r) @ m
    T = np.eye(4)
    T[:3, 3] = t
    return T @ m


@functools.lru_cache(maxsize=16)
def _rig(species):
    """Parse a GLB once → the rig (rest pose, hierarchy, skin, per-primitive
    vertex data, and every clip's channels). None if unavailable."""
    if not _OK:
        return None
    base = cg.SPECIES_GLB.get((species or "").lower())
    import os
    path = os.path.join(cg._DIR, (base or "") + ".glb")
    if not base or not os.path.exists(path):
        return None
    try:
        import pygltflib as gl
        g = gl.GLTF2().load(path)
        blob = g.binary_blob()
        rest, children = {}, {}
        for i, n in enumerate(g.nodes):
            rest[i] = (list(n.translation or [0, 0, 0]),
                       list(n.rotation or [0, 0, 0, 1]),
                       list(n.scale or [1, 1, 1]))
            children[i] = list(n.children or [])
        roots = list(g.scenes[g.scene or 0].nodes or [])
        skin = g.skins[0]
        invb = cg._acc(g, blob, skin.inverseBindMatrices
                       ).reshape(-1, 4, 4).transpose(0, 2, 1).astype(float)
        joints = list(skin.joints)
        prims = []
        for i, n in enumerate(g.nodes):
            if n.mesh is None:
                continue
            for pr in g.meshes[n.mesh].primitives:
                if pr.attributes.POSITION is None or pr.indices is None:
                    continue
                pos = cg._acc(g, blob, pr.attributes.POSITION).astype(float)
                idx = cg._acc(g, blob, pr.indices).reshape(-1, 3).astype(np.int64)
                col = cg._mat_color(g, pr)
                skinned = (n.skin is not None
                           and pr.attributes.JOINTS_0 is not None)
                J = W = None
                if skinned:
                    J = cg._acc(g, blob, pr.attributes.JOINTS_0).astype(int)
                    W = cg._acc(g, blob, pr.attributes.WEIGHTS_0).astype(float)
                prims.append((i, skinned, pos, idx, col, J, W))
        clips, dur = {}, {}
        for a in (g.animations or []):
            name = a.name
            if name is None or "|" in name:           # skip the duped 'Armature|…'
                continue
            ch = {}
            tmax = 0.0
            for c in a.channels:
                s = a.samplers[c.sampler]
                times = cg._acc(g, blob, s.input).reshape(-1).astype(float)
                vals = cg._acc(g, blob, s.output).astype(float)
                ch.setdefault(c.target.node, {})[c.target.path] = (times, vals)
                tmax = max(tmax, float(times[-1]) if len(times) else 0.0)
            clips[name] = ch
            dur[name] = tmax or 1.0
        return {"rest": rest, "children": children, "roots": roots,
                "invb": invb, "joints": joints, "prims": prims,
                "clips": clips, "dur": dur}
    except Exception:
        return None


def _sample(ch, node, path, t, default):
    if node not in ch or path not in ch[node]:
        return default
    times, vals = ch[node][path]
    if t <= times[0]:
        return list(vals[0])
    if t >= times[-1]:
        return list(vals[-1])
    k = int(np.searchsorted(times, t)) - 1
    k = max(0, min(k, len(times) - 2))
    a = (t - times[k]) / (times[k + 1] - times[k])
    if path == "rotation":                       # nlerp along the short arc
        q0, q1 = vals[k].astype(float), vals[k + 1].astype(float)
        if np.dot(q0, q1) < 0:
            q1 = -q1
        v = q0 * (1 - a) + q1 * a
        v = v / (np.linalg.norm(v) or 1.0)
        return list(v)
    return list(vals[k] * (1 - a) + vals[k + 1] * a)


def _world_mats(rig, clip, t):
    ch = rig["clips"][clip]
    rest, children = rig["rest"], rig["children"]
    out = {}

    def walk(ni, parent):
        T, R, S = rest[ni]
        local = _trs(_sample(ch, ni, "translation", t, T),
                     _sample(ch, ni, "rotation", t, R),
                     _sample(ch, ni, "scale", t, S))
        w = parent @ local
        out[ni] = w
        for c in children[ni]:
            walk(c, w)

    eye = np.eye(4)
    for ni in rig["roots"]:
        walk(ni, eye)
    return out


def _frame_meshes(rig, clip, t):
    W = _world_mats(rig, clip, t)
    joints, invb = rig["joints"], rig["invb"]
    jm = np.stack([W[joints[j]] @ invb[j] for j in range(len(joints))])
    meshes = []
    for node, skinned, pos, idx, col, J, Wt in rig["prims"]:
        if skinned:
            hp = np.concatenate([pos, np.ones((len(pos), 1))], 1)
            acc = np.zeros((len(pos), 3))
            for k in range(4):
                m = jm[J[:, k]]                       # (N,4,4)
                acc += Wt[:, k:k + 1] * np.einsum("nij,nj->ni", m, hp)[:, :3]
            meshes.append((acc, idx, col))
        else:
            w = W.get(node)
            if w is None:
                continue
            meshes.append((pos @ w[:3, :3].T + w[:3, 3], idx, col))
    return meshes


@functools.lru_cache(maxsize=4096)
def _frame_sprite(species, clip, frame, nframes, size, angle):
    rig = _rig(species)
    if not rig or clip not in rig["clips"]:
        return None
    try:
        t = rig["dur"][clip] * (frame / nframes)
        meshes = _frame_meshes(rig, clip, t)
        return r3.bake(cg._normalise(meshes, angle), int(size))
    except Exception:
        return None


def clip_for(species, action):
    rig = _rig(species)
    if not rig:
        return None
    avail = rig["clips"]
    for name in _CLIP_PREF.get(action, []):
        if name in avail:
            return name
    if "Idle" in avail:
        return "Idle"
    return next(iter(avail), None)


def _action_and_phase(char):
    """(action, phase 0..1) from the shared `_anim` state."""
    a = (getattr(char, "metadata", None) or {}).get("_anim", {}) or {}
    alive = True
    try:
        alive = char.is_alive()
    except Exception:
        pass
    if not alive or (getattr(char, "metadata", None) or {}).get("dying"):
        return "dead", 1.0
    if a.get("atk_t", 0) > 0:
        return "attack", max(0.0, min(1.0, 1.0 - a["atk_t"] / _ATTACK_DUR))
    if a.get("cur_action") == "hurt" and a.get("action_dur"):
        return "hurt", max(0.0, min(1.0, 1.0 - a.get("action_t", 0) / a["action_dur"]))
    if a.get("moving"):
        return "walk", (a.get("move_phase", a.get("walk_phase", 0.0)) % 1.0)
    return "idle", (a.get("idle_phase", 0.0) % math.tau) / math.tau


def animated_sprite(char, size, face_east=False):
    """A baked, ANIMATED model frame for `char`'s current action, or None (→ the
    caller uses the static bind-pose sprite / procedural creature)."""
    if not _OK:
        return None
    species = cg.species_of(char)
    if species is None:
        return None
    action, phase = _action_and_phase(char)
    clip = clip_for(species, action)
    if clip is None:
        return None
    # a one-shot (attack/hurt) holds its last frame; a loop wraps
    frame = int(phase * NFRAMES)
    frame = min(frame, NFRAMES - 1) if action in ("attack", "hurt", "dead") \
        else frame % NFRAMES
    spr = _frame_sprite(species, clip, frame, NFRAMES, int(size), cg._FACING)
    if spr is None:
        return None
    if face_east:
        try:
            import pygame
            return pygame.transform.flip(spr, True, False)
        except Exception:
            return spr
    return spr
