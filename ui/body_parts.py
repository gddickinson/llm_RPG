"""P33.4b body parts — the thin pygame drawing of a posed character.

Each function takes the `char_pose.build_pose` joint dict + colours and blits
one part with rounded (circle-capped) limbs, a filled torso, a haired head with
a face, and a weapon/shield aligned to the arm. Kept separate so `body_renderer`
stays orchestration and every file holds under 500 lines.
"""

import math


def _pt(p):
    return (int(round(p[0])), int(round(p[1])))


def _dark(c, a=40):
    return tuple(max(0, x - a) for x in c[:3])


def _limb(surface, p0, p1, color, w):
    import pygame
    a, b = _pt(p0), _pt(p1)
    pygame.draw.line(surface, color, a, b, max(1, w))
    pygame.draw.circle(surface, color, b, max(1, w // 2))


def draw_legs(surface, pose, pants, boots, w):
    import pygame
    for hip, knee, foot in (("l_hip", "l_knee", "l_foot"),
                            ("r_hip", "r_knee", "r_foot")):
        _limb(surface, pose[hip], pose[knee], pants, w)
        _limb(surface, pose[knee], pose[foot], pants, w)
        fx, fy = _pt(pose[foot])
        pygame.draw.ellipse(surface, boots,
                            (fx - w, fy - max(1, w // 2), w * 2, w))


def draw_torso(surface, pose, color, belt):
    import pygame
    lh, rh = pose["l_hip"], pose["r_hip"]
    ls, rs = pose["l_sh"], pose["r_sh"]
    # a rounded BARREL (P33.6a) — the sides bulge by the character's girth
    girth = pose.get("girth", 1.0)
    my = (ls[1] + lh[1]) / 2
    bulge = (max(rh[0], rs[0]) - min(lh[0], ls[0])) * 0.16 * girth
    left = (min(lh[0], ls[0]) - bulge, my)
    right = (max(rh[0], rs[0]) + bulge, my)
    pts = [_pt(lh), _pt(left), _pt(ls), _pt(rs), _pt(right), _pt(rh)]
    pygame.draw.polygon(surface, color, pts)
    pygame.draw.polygon(surface, _dark(color, 55), pts, 1)
    pygame.draw.line(surface, belt, _pt(lh), _pt(rh), max(2, int(bulge)))


def draw_arms(surface, pose, sleeve, skin, w):
    _limb(surface, pose["l_sh"], pose["l_elbow"], sleeve, w)
    _limb(surface, pose["l_elbow"], pose["l_hand"], skin, max(1, w - 1))
    _limb(surface, pose["r_sh"], pose["r_elbow"], sleeve, w)
    _limb(surface, pose["r_elbow"], pose["r_hand"], skin, max(1, w - 1))


def draw_head(surface, pose, skin, hair, race, face_visible, neck_w, profile=0):
    import pygame
    hx, hy = _pt(pose["head"])
    r = pose["head_r"]
    pygame.draw.line(surface, skin, _pt(pose["neck"]), (hx, hy), max(2, neck_w))
    pygame.draw.circle(surface, skin, (hx, hy), r)
    pygame.draw.circle(surface, _dark(skin, 55), (hx, hy), r, 1)
    if race in ("elf", "half-elf"):
        for s in (-1, 1):
            pygame.draw.polygon(surface, skin, [
                (hx + s * r, hy), (hx + s * (r + r // 2), hy - r // 2),
                (hx + s * r, hy - r // 3)])
    elif race in ("orc", "half-orc", "goblin"):
        for s in (-1, 1):
            pygame.draw.line(surface, (225, 225, 205),
                             (hx + s, hy + r - 1), (hx + s, hy + r + 2), 1)
    if not face_visible:
        pygame.draw.circle(surface, hair, (hx, hy), r)      # back of the head
        return
    # hair cap on top; the lower face stays skin
    pygame.draw.circle(surface, hair, (hx, hy - max(1, r // 2)), r)
    e = max(1, r // 5)
    if profile:                                             # side: nose + 1 eye
        pygame.draw.circle(surface, skin,
                           (hx + profile * (r // 3), hy + r // 3), max(1, r * 2 // 3))
        nx = hx + profile * r
        pygame.draw.polygon(surface, skin, [
            (nx, hy - 1), (nx + profile * max(1, r // 3), hy + r // 4),
            (nx, hy + r // 3)])
        pygame.draw.circle(surface, (35, 30, 28),
                           (hx + profile * (r // 3), hy + r // 6), e)
    else:                                                   # front: two eyes
        pygame.draw.circle(surface, skin, (hx, hy + r // 3), max(1, r * 2 // 3))
        for s in (-1, 1):
            pygame.draw.circle(surface, (35, 30, 28),
                               (hx + s * (r // 3), hy + r // 5), e)


def draw_shield(surface, pose, face, rim, r):
    import pygame
    hx, hy = _pt(pose["l_hand"])
    pygame.draw.circle(surface, face, (hx, hy), r)
    pygame.draw.circle(surface, rim, (hx, hy), r, max(1, r // 4))
    pygame.draw.circle(surface, rim, (hx, hy), max(1, r // 3))


def draw_weapon(surface, weapon, pose, length, w):
    """Draw the weapon from the RIGHT hand, aligned along the forearm."""
    import pygame
    hand = pose["r_hand"]
    elbow = pose["r_elbow"]
    dx, dy = hand[0] - elbow[0], hand[1] - elbow[1]
    d = math.hypot(dx, dy) or 1.0
    ux, uy = dx / d, dy / d                      # forearm direction (out of hand)
    hx, hy = _pt(hand)
    tip = (int(hand[0] + ux * length), int(hand[1] + uy * length))
    px, py = -uy, ux                             # perpendicular
    steel, wood = (222, 224, 232), (140, 100, 62)
    if weapon in ("sword", "dagger"):
        blade = length if weapon == "sword" else length * 0.55
        tip = (int(hand[0] + ux * blade), int(hand[1] + uy * blade))
        pygame.draw.line(surface, steel, (hx, hy), tip, max(2, w))
        g = int(length * 0.18)
        pygame.draw.line(surface, (120, 90, 55),
                         (hx - int(px * g), hy - int(py * g)),
                         (hx + int(px * g), hy + int(py * g)), max(2, w))
    elif weapon == "axe":
        pygame.draw.line(surface, wood, (hx, hy), tip, max(2, w))
        b = int(length * 0.30)
        pygame.draw.polygon(surface, (205, 208, 214), [
            tip, (int(tip[0] + px * b), int(tip[1] + py * b)),
            (int(tip[0] - ux * b), int(tip[1] - uy * b))])
    elif weapon == "mace":
        pygame.draw.line(surface, wood, (hx, hy), tip, max(2, w))
        pygame.draw.circle(surface, (188, 190, 200), tip, max(2, int(length * 0.2)))
    elif weapon == "spear":
        tip = (int(hand[0] + ux * length * 1.4), int(hand[1] + uy * length * 1.4))
        pygame.draw.line(surface, wood, (hx, hy), tip, max(2, w))
        pygame.draw.polygon(surface, steel, [
            tip, (int(tip[0] - ux * 5 + px * 3), int(tip[1] - uy * 5 + py * 3)),
            (int(tip[0] - ux * 5 - px * 3), int(tip[1] - uy * 5 - py * 3))])
    elif weapon == "staff":
        tip = (int(hand[0] + ux * length * 1.2), int(hand[1] + uy * length * 1.2))
        pygame.draw.line(surface, (120, 86, 52), (hx, hy), tip, max(2, w))
        pygame.draw.circle(surface, (120, 190, 255), tip, max(2, int(length * 0.16)))
    elif weapon == "bow":
        r = max(3, int(length * 0.42))
        base = math.atan2(uy, ux)
        rect = (hx - r, hy - r, r * 2, r * 2)
        pygame.draw.arc(surface, (150, 100, 55), rect,
                        base - 1.1, base + 1.1, max(2, w))
        # bowstring across the arc's ends
        p1 = (hx + int(r * math.cos(base - 1.1)), hy + int(r * math.sin(base - 1.1)))
        p2 = (hx + int(r * math.cos(base + 1.1)), hy + int(r * math.sin(base + 1.1)))
        pygame.draw.line(surface, (225, 220, 195), p1, p2, 1)
