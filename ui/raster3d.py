"""P41.2 — a compact numpy SOFTWARE 3D rasterizer (ported from movieMaker's
`mm/studio/raster3d.py`), + a `bake` that renders a mesh ONCE to a cached iso
sprite.

`render(meshes, cam…) -> (rgb uint8 HxWx3, mask bool HxW)` z-buffers Lambert-
shaded, back-face-culled triangles through a pinhole camera — no GPU, headless.
Because the game's camera angle is FIXED, `bake(meshes, size)` runs it once per
object and returns a pygame sprite the renderer blits like any 2D image, so the
"3D-look" objects cost nothing per frame. Mesh = (verts Nx3, tris Mx3, rgb).
"""

import math

import numpy as np

# a fixed 3/4 iso-ish camera framing a unit object centred near the origin,
# sitting on the y=0 ground — the angle the whole world bakes at (P41.2)
ISO_CAM = (2.6, 3.0, -3.0)
ISO_LOOK = (0.0, 0.45, 0.0)
ISO_VFOV = 40.0
LIGHT_DIR = (-0.5, -1.0, -0.35)
FILL_DIR = (0.7, -0.25, 0.55)          # ISO.3 a soft fill from the other side


def box(cx, cy, cz, w, h, d, color):
    """An axis-aligned box: base centre (cx,cz) on the ground, rising `h`."""
    x0, x1 = cx - w / 2, cx + w / 2
    z0, z1 = cz - d / 2, cz + d / 2
    y0, y1 = cy, cy + h
    v = np.array([[x0, y0, z0], [x1, y0, z0], [x1, y0, z1], [x0, y0, z1],
                  [x0, y1, z0], [x1, y1, z0], [x1, y1, z1], [x0, y1, z1]],
                 float)
    t = np.array([[0, 2, 1], [0, 3, 2], [4, 5, 6], [4, 6, 7],
                  [0, 1, 5], [0, 5, 4], [1, 2, 6], [1, 6, 5],
                  [2, 3, 7], [2, 7, 6], [3, 0, 4], [3, 4, 7]])
    return v, t, color


def roof(cx, cy, cz, w, h, d, color):
    """A pitched-gable prism sitting at height cy, ridge along the x axis."""
    x0, x1 = cx - w / 2, cx + w / 2
    z0, z1 = cz - d / 2, cz + d / 2
    v = np.array([[x0, cy, z0], [x1, cy, z0], [x1, cy, z1], [x0, cy, z1],
                  [x0, cy + h, cz], [x1, cy + h, cz]], float)
    t = np.array([[0, 4, 1], [3, 2, 5], [0, 3, 5], [0, 5, 4],
                  [1, 4, 5], [1, 5, 2]])
    return v, t, color


def taper(a, b, r0, r1, color, seg=8):
    """A tapered round tube (frustum) from point `a` (radius r0) to `b` (r1) —
    a limb segment that swells at the joint and narrows toward the end. ISO.10."""
    a = np.asarray(a, float)
    b = np.asarray(b, float)
    axis = b - a
    d = axis / (np.linalg.norm(axis) or 1e-6)
    up = np.array([0, 0, 1.0]) if abs(d[1]) > 0.9 else np.array([0, 1.0, 0])
    p1 = np.cross(d, up)
    p1 /= (np.linalg.norm(p1) or 1.0)
    p2 = np.cross(d, p1)
    ang = 2 * math.pi * np.arange(seg) / seg
    ring = np.cos(ang)[:, None] * p1 + np.sin(ang)[:, None] * p2
    v = np.vstack([a + ring * r0, b + ring * r1, a, b])
    t = []
    for i in range(seg):
        j = (i + 1) % seg
        t += [[i, j, seg + i], [j, seg + j, seg + i],
              [2 * seg, j, i], [2 * seg + 1, seg + i, seg + j]]
    return v, np.array(t), tuple(int(c) for c in color)


def ball(c, r, color, seg=6):
    """A low-res UV sphere — a joint, a head, a hand. ISO.10."""
    c = np.asarray(c, float)
    v = []
    rings = []
    for iy in range(seg + 1):
        phi = math.pi * iy / seg
        y, rr = math.cos(phi), math.sin(phi)
        row = []
        for ix in range(seg):
            th = 2 * math.pi * ix / seg
            row.append(len(v))
            v.append(c + r * np.array([rr * math.cos(th), y, rr * math.sin(th)]))
        rings.append(row)
    t = []
    for iy in range(seg):
        for ix in range(seg):
            a, b = rings[iy][ix], rings[iy][(ix + 1) % seg]
            cc, dd = rings[iy + 1][ix], rings[iy + 1][(ix + 1) % seg]
            t += [[a, b, cc], [b, dd, cc]]
    return np.array(v), np.array(t), tuple(int(x) for x in color)


def render(meshes, cam_pos=ISO_CAM, look=ISO_LOOK, up=(0.0, 1.0, 0.0),
           vfov_deg=ISO_VFOV, width=64, height=64, light_dir=LIGHT_DIR):
    """meshes: [(verts Nx3, tris Mx3, rgb)] -> (rgb uint8, mask bool)."""
    rgb = np.zeros((height, width, 3), np.uint8)
    mask = np.zeros((height, width), bool)
    zbuf = np.full((height, width), np.inf)
    cam = np.array(cam_pos, float)
    fwd = np.array(look, float) - cam
    fwd /= (np.linalg.norm(fwd) or 1.0)
    right = np.cross(fwd, up)
    right /= (np.linalg.norm(right) or 1.0)
    upv = np.cross(right, fwd)
    th = math.tan(math.radians(vfov_deg) / 2.0)
    aspect = width / height
    ld = np.array(light_dir, float)
    ld /= (np.linalg.norm(ld) or 1.0)
    fd = np.array(FILL_DIR, float)                 # ISO.3 soft fill light
    fd /= (np.linalg.norm(fd) or 1.0)
    for verts, tris, color in meshes:
        verts = np.asarray(verts, float)
        tris = np.asarray(tris)
        if len(tris) == 0 or len(verts) == 0:
            continue
        rel = verts - cam
        zc = rel @ fwd
        with np.errstate(divide="ignore", invalid="ignore"):
            sx = width * 0.5 + (rel @ right / (zc * th * aspect)) * width * 0.5
            sy = height * 0.5 - (rel @ upv / (zc * th)) * height * 0.5
        a, b, c = verts[tris[:, 0]], verts[tris[:, 1]], verts[tris[:, 2]]
        nrm = np.cross(b - a, c - a)
        nl = np.linalg.norm(nrm, axis=1)
        good = nl > 1e-9
        nrm[good] /= nl[good][:, None]
        centre = (a + b + c) / 3.0
        facing = np.einsum("ij,ij->i", nrm, cam - centre) > 0
        lam = np.clip(-(nrm @ ld), 0.0, 1.0)       # key light
        lam2 = np.clip(-(nrm @ fd), 0.0, 1.0)      # ISO.3 soft fill light
        shade = np.clip(0.30 + 0.55 * lam + 0.15 * lam2, 0.0, 1.0)
        valid = good & facing & (zc[tris[:, 0]] > 0.02) \
            & (zc[tris[:, 1]] > 0.02) & (zc[tris[:, 2]] > 0.02)
        col = np.array(color, float)
        for ti in np.nonzero(valid)[0]:
            i, j, k = tris[ti]
            _fill(rgb, mask, zbuf, sx, sy, zc, i, j, k, width, height,
                  col * shade[ti])
    return rgb, mask


def _fill(rgb, mask, zbuf, sx, sy, zc, i, j, k, w, h, shade):
    ax, ay, bx, by, cx, cy = sx[i], sy[i], sx[j], sy[j], sx[k], sy[k]
    minx = max(0, int(math.floor(min(ax, bx, cx))))
    maxx = min(w - 1, int(math.ceil(max(ax, bx, cx))))
    miny = max(0, int(math.floor(min(ay, by, cy))))
    maxy = min(h - 1, int(math.ceil(max(ay, by, cy))))
    if minx > maxx or miny > maxy:
        return
    denom = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
    if abs(denom) < 1e-9:
        return
    xx, yy = np.meshgrid(np.arange(minx, maxx + 1), np.arange(miny, maxy + 1))
    w0 = ((by - cy) * (xx - cx) + (cx - bx) * (yy - cy)) / denom
    w1 = ((cy - ay) * (xx - cx) + (ax - cx) * (yy - cy)) / denom
    w2 = 1.0 - w0 - w1
    ins = (w0 >= -1e-4) & (w1 >= -1e-4) & (w2 >= -1e-4)
    zz = w0 * zc[i] + w1 * zc[j] + w2 * zc[k]
    reg = zbuf[miny:maxy + 1, minx:maxx + 1]
    upd = ins & (zz < reg)
    if not upd.any():
        return
    reg[upd] = zz[upd]
    px = np.clip(shade, 0, 255).astype(np.uint8)
    rgb[miny:maxy + 1, minx:maxx + 1][upd] = px
    mask[miny:maxy + 1, minx:maxx + 1][upd] = True


# ISO.5 supersample factor for the bake — renders at SSAA× then smoothscales
# down for crisper silhouettes + finer detail (cost is one-time per cache key).
# Overridable via LLM_RPG_ISO_SS (clamped 2..4).
def _ssaa() -> int:
    import os
    try:
        return max(2, min(4, int(os.environ.get("LLM_RPG_ISO_SS", "3"))))
    except Exception:
        return 3


def bake(meshes, size=64, **cam):
    """Render `meshes` once at the iso camera → a pygame RGBA sprite (cached by
    the caller). Antialiased by rendering at SSAA× and smooth-scaling down."""
    import pygame
    ss = size * _ssaa()
    rgb, mask = render(meshes, width=ss, height=ss, **cam)
    rgba = np.zeros((ss, ss, 4), np.uint8)
    rgba[..., :3] = rgb
    rgba[..., 3] = mask.astype(np.uint8) * 255           # (H, W, 4) row-major
    surf = pygame.image.frombuffer(
        np.ascontiguousarray(rgba).tobytes(), (ss, ss), "RGBA").copy()
    return pygame.transform.smoothscale(surf, (size, size))
