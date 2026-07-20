"""ISO.12 — worn GEAR for the isometric characters: the weapon in hand, a shield
on the off-arm, and headgear (helmet / wizard hat / hood / circlet).

George: "add variety to the iso characters — different body types, different
weapons, different clothing and armour." The body types + tunic colour live in
`iso_skeleton`; this module builds the accessory meshes (baked into the same
cached sprite as the body) so a warrior reads a helmet + sword + shield, a wizard
a pointed hat + staff, a ranger a hood + bow. Pure geometry over `raster3d`.
"""

import math

import numpy as np

from ui import raster3d as r3

_STEEL = (198, 204, 214)
_WOOD = (122, 86, 52)
_DARK = (58, 52, 48)
_GOLD = (202, 170, 72)
_CLOTH = (92, 72, 112)
_LEATHER = (96, 74, 52)


def _seg(a, d, length, r, color):
    """A round shaft/blade of radius `r` from point `a` along unit dir `d`."""
    return r3.taper(a, a + d * length, r, r, color, 5)


def _cone(base, up, h, r, color):
    return r3.taper(base, base + up * h, r, 0.006, color, 6)


def weapon_mesh(kind, hand, fwd):
    """The weapon gripped at `hand`, held UP-and-FORWARD (a ready stance) so it
    reads at any pose; it tracks the hand through the animation."""
    up = np.array([0.0, 1.0, 0.0])
    d = up * 0.75 + fwd * 0.5
    d /= (np.linalg.norm(d) or 1.0)
    perp = np.cross(d, up)
    perp = perp / (np.linalg.norm(perp) or 1.0) if np.linalg.norm(perp) > 1e-3 \
        else fwd
    g = np.asarray(hand, float)
    if kind == "sword":
        return [_seg(g - d * 0.05, d, 0.15, 0.022, _DARK),
                r3.box(*(g + d * 0.12), 0.16, 0.035, 0.05, _GOLD),
                _seg(g + d * 0.14, d, 0.66, 0.024, _STEEL)]
    if kind == "dagger":
        return [_seg(g - d * 0.04, d, 0.09, 0.022, _DARK),
                _seg(g + d * 0.06, d, 0.26, 0.022, _STEEL)]
    if kind == "axe":
        head = g + d * 0.6
        return [_seg(g - d * 0.1, d, 0.72, 0.024, _WOOD),
                r3.box(head[0] + perp[0] * 0.06, head[1],
                       head[2] + perp[2] * 0.06, 0.13, 0.17, 0.05, _STEEL)]
    if kind == "mace":
        return [_seg(g - d * 0.05, d, 0.52, 0.024, _WOOD),
                r3.ball(g + d * 0.52, 0.075, _STEEL, 5)]
    if kind == "spear":
        return [_seg(g - d * 0.45, d, 1.25, 0.019, _WOOD),
                _seg(g + d * 0.78, d, 0.15, 0.032, _STEEL)]
    if kind == "staff":
        return [_seg(g - d * 0.4, d, 1.2, 0.024, _WOOD),
                r3.ball(g + d * 0.78, 0.055, _GOLD, 5)]
    if kind == "bow":                       # a vertical limb in the off-hand
        vp = [g + up * 0.44, g + up * 0.28 + fwd * 0.05, g + fwd * 0.015,
              g - up * 0.28 + fwd * 0.05, g - up * 0.44]
        m = []
        for i in range(len(vp) - 1):
            v = vp[i + 1] - vp[i]
            length = float(np.linalg.norm(v))
            if length > 1e-4:
                m.append(_seg(vp[i], v / length, length, 0.013, _WOOD))
        v = vp[-1] - vp[0]
        length = float(np.linalg.norm(v)) or 1.0
        m.append(_seg(vp[0], v / length, length, 0.004, (230, 230, 220)))
        return m
    return []


def headgear_mesh(kind, hc, fwd):
    """Headgear centred on the head `hc`: a metal helmet, a wizard's pointed hat,
    a drawn hood, or a noble's circlet."""
    up = np.array([0.0, 1.0, 0.0])
    if kind == "helmet":
        return [r3.ball(hc + up * 0.03, 0.125, _STEEL, 7),
                r3.box(hc[0] + fwd[0] * 0.11, hc[1] - 0.02, hc[2] + fwd[2] * 0.11,
                       0.04, 0.11, 0.05, _STEEL)]          # nasal guard
    if kind == "hat":
        return [_cone(hc + up * 0.06, up, 0.42, 0.135, _CLOTH),
                r3.taper(hc + up * 0.05, hc + up * 0.09, 0.15, 0.15, _DARK, 7)]
    if kind == "hood":
        return [r3.ball(hc + up * 0.02 - fwd * 0.02, 0.135, (70, 66, 60), 6)]
    if kind == "circlet":
        return [r3.taper(hc + up * 0.07, hc + up * 0.085,
                         0.116, 0.116, _GOLD, 8)]
    return []


def shield_mesh(lhand, fwd):
    """A round shield on the off-hand."""
    lh = np.asarray(lhand, float)
    return [r3.taper(lh + fwd * 0.02, lh + fwd * 0.04, 0.14, 0.14, _LEATHER, 8),
            r3.ball(lh + fwd * 0.03, 0.03, _GOLD, 5)]


def pauldron_mesh(P):
    """H1: armored shoulder plates (heavy classes) — a steel cap on each shoulder
    (iso parity with the top-down G5 pauldrons)."""
    m = []
    for s in ("l_sh", "r_sh"):
        sh = np.asarray(P[s], float)
        m.append(r3.ball(sh + np.array([0.0, 0.035, 0.0]), 0.078, _STEEL, 6))
    return m


def accessories(P, angle, kit):
    """Assemble the worn gear for the pose `P` from a `kit` tuple
    (weapon, head, shield, height)."""
    weapon, head, shield = kit[0], kit[1], kit[2]
    fwd = np.array([math.sin(angle), 0.0, math.cos(angle)])
    m = []
    if weapon == "bow":
        m += weapon_mesh("bow", P["l_hand"], fwd)
    elif weapon:
        m += weapon_mesh(weapon, P["r_hand"], fwd)
    if shield and weapon != "bow":
        m += shield_mesh(P["l_hand"], fwd)
    if head:
        m += headgear_mesh(head, P["head"] + np.array([0.0, -0.01, 0.0]), fwd)
    if len(kit) > 5 and kit[5]:                  # H1 armored shoulder plates
        m += pauldron_mesh(P)
    return m
