"""P33.4b body parts — the thin pygame drawing of a posed character.

Each function takes the `char_pose.build_pose` joint dict + colours and blits
one part with rounded (circle-capped) limbs, a filled torso, a haired head with
a face, and a weapon/shield aligned to the arm. Kept separate so `body_renderer`
stays orchestration and every file holds under 500 lines.
"""

import math

# R1 realism: a screen-space KEY LIGHT from the top-left. Every body part is shaded
# as a rounded form against it — a dark side away from the light, a lit core, and a
# bright edge toward it — so limbs read as cylinders and the head as a sphere.
_LIGHT = (-0.72, -0.69)


def _pt(p):
    return (int(round(p[0])), int(round(p[1])))


def _dark(c, a=40):
    return tuple(max(0, x - a) for x in c[:3])


def _lighten(c, a=45):
    return tuple(min(255, x + a) for x in c[:3])


def _limb(surface, p0, p1, color, w):
    """R1: a SHADED CYLINDER — a full-width dark underside, the core shifted toward
    the light (leaving a shadow rim), and a bright highlight stripe on the lit edge.
    A limb reads round, not a flat stick."""
    import pygame
    a, b = _pt(p0), _pt(p1)
    w = max(2, int(w))
    dx, dy = b[0] - a[0], b[1] - a[1]
    L = math.hypot(dx, dy) or 1.0
    px, py = -dy / L, dx / L                        # perpendicular to the limb
    if px * _LIGHT[0] + py * _LIGHT[1] < 0:         # point it toward the light
        px, py = -px, -py
    off = w * 0.30
    pygame.draw.line(surface, _dark(color, 46), a, b, w)     # 1) dark underside
    pygame.draw.circle(surface, _dark(color, 46), b, max(1, w // 2))
    ca = _pt((a[0] + px * off * 0.45, a[1] + py * off * 0.45))
    cb = _pt((b[0] + px * off * 0.45, b[1] + py * off * 0.45))
    cw = max(1, int(w * 0.80))
    pygame.draw.line(surface, color, ca, cb, cw)            # 2) lit core
    pygame.draw.circle(surface, color, cb, max(1, cw // 2))
    ha = _pt((a[0] + px * off, a[1] + py * off))
    hb = _pt((b[0] + px * off, b[1] + py * off))
    pygame.draw.line(surface, _lighten(color, 42), ha, hb,  # 3) highlight stripe
                     max(1, int(w * 0.32)))


def _bow(p0, pj, p1, amt):
    """P34.6: push the joint out from the straight p0→p1 line so the limb ARCS
    (an elbow/knee bends, not a stick). Amplifies its existing deviation."""
    mx, my = (p0[0] + p1[0]) / 2.0, (p0[1] + p1[1]) / 2.0
    return (pj[0] + (pj[0] - mx) * amt, pj[1] + (pj[1] - my) * amt)


def draw_legs(surface, pose, pants, boots, w):
    import pygame
    for hip, knee, foot in (("l_hip", "l_knee", "l_foot"),
                            ("r_hip", "r_knee", "r_foot")):
        kn = _bow(pose[hip], pose[knee], pose[foot], 0.30)      # knee bows forward
        _limb(surface, pose[hip], kn, pants, w)
        _limb(surface, kn, pose[foot], pants, w)
        fx, fy = _pt(pose[foot])
        # G4 a directional BOOT — the toe extends toward the facing (a clear
        # silhouette cue), rounder + toward-camera when facing front
        prof = pose.get("fdir", 0) or pose.get("profile", 0)
        toe = int(w * 0.85)
        if prof > 0:                                  # facing screen-right
            rect = (fx - w // 2, fy - max(1, w // 2), w + toe, w)
        elif prof < 0:                                # facing screen-left
            rect = (fx - w // 2 - toe, fy - max(1, w // 2), w + toe, w)
        else:                                         # facing the camera
            rect = (fx - w, fy - max(1, w // 2), w * 2, int(w * 1.25))
        pygame.draw.ellipse(surface, boots, rect)
        pygame.draw.ellipse(surface, _lighten(boots, 20), rect, 1)


# R5: classes that wear a robe/gown — the legs read as a hanging SKIRT, not pants
ROBE_CLASSES = {"wizard", "sorcerer", "warlock", "cleric", "druid", "monk",
                "necromancer", "priest"}


def draw_robe(surface, pose, color, w):
    """R5: a flared, shaded SKIRT from the hips to the ankles — a robe reads as
    hanging cloth (lit flank, shadow flank, a dark hem, a couple of folds) that
    sways a little with the feet, instead of bare legs."""
    import pygame
    lh, rh = pose["l_hip"], pose["r_hip"]
    lf, rf = pose["l_foot"], pose["r_foot"]
    hem_y = max(lf[1], rf[1])
    flare = abs(rh[0] - lh[0]) * 0.6 + w
    hemL = (min(lf[0], lh[0]) - flare, hem_y)
    hemR = (max(rf[0], rh[0]) + flare, hem_y)
    pts = [_pt(lh), _pt(hemL), _pt(hemR), _pt(rh)]
    pygame.draw.polygon(surface, color, pts)
    pygame.draw.line(surface, _lighten(color, 26), _pt(lh), _pt(hemL), max(2, w))
    pygame.draw.line(surface, _dark(color, 34), _pt(rh), _pt(hemR), max(2, w))
    pygame.draw.line(surface, _dark(color, 30), _pt(hemL), _pt(hemR),
                     max(2, w // 2 + 1))
    for t in (0.34, 0.66):                              # fold lines
        top = (lh[0] + (rh[0] - lh[0]) * t, lh[1])
        bot = (hemL[0] + (hemR[0] - hemL[0]) * t, hem_y)
        pygame.draw.line(surface, _dark(color, 22), _pt(top), _pt(bot), 1)


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
    # R1 form: the lit (screen-left) flank catches light, the far flank falls to
    # shadow — the barrel reads round; a dark rim seats it
    th = max(2, int(abs(lh[1] - ls[1]) * 0.32))
    pygame.draw.line(surface, _lighten(color, 30), _pt(left), _pt(ls), th)
    pygame.draw.line(surface, _dark(color, 34), _pt(right), _pt(rs), th)
    pygame.draw.polygon(surface, _dark(color, 62), pts, 1)
    pygame.draw.line(surface, belt, _pt(lh), _pt(rh), max(2, int(bulge)))


def draw_arms(surface, pose, sleeve, skin, w):
    draw_arm(surface, pose, "l", sleeve, skin, w)
    draw_arm(surface, pose, "r", sleeve, skin, w)


def draw_arm(surface, pose, side, sleeve, skin, w):
    """One arm (P34.14 depth-sort: the far arm is drawn behind the torso;
    P34.6: the elbow bows so the arm arcs). G4: a small HAND caps the wrist."""
    import pygame
    sh, el, ha = side + "_sh", side + "_elbow", side + "_hand"
    eb = _bow(pose[sh], pose[el], pose[ha], 0.30)
    _limb(surface, pose[sh], eb, sleeve, w)
    _limb(surface, eb, pose[ha], skin, max(1, w - 1))
    hx, hy = _pt(pose[ha])                       # G4 a rounded hand + a lit knuckle
    hr = max(2, int(w * 0.72))
    pygame.draw.circle(surface, skin, (hx, hy), hr)
    pygame.draw.circle(surface, _lighten(skin, 26),
                       (hx - max(1, hr // 3), hy - max(1, hr // 3)), max(1, hr // 2))


def draw_head(surface, pose, skin, hair, race, face_visible, neck_w, profile=0,
              expr="neutral", blink=False, look=(0.0, 0.0)):
    import pygame
    hx, hy = _pt(pose["head"])
    r = pose["head_r"]
    pygame.draw.line(surface, skin, _pt(pose["neck"]), (hx, hy), max(2, neck_w))
    # R1 spherical head: a dark base, the core shifted toward the light (leaving a
    # shadow crescent), and a highlight — so the head reads as a ball, not a disc
    pygame.draw.circle(surface, _dark(skin, 42), (hx, hy), r)
    pygame.draw.circle(surface, skin,
                       (hx - int(r * 0.15), hy - int(r * 0.15)), max(1, int(r * 0.90)))
    pygame.draw.circle(surface, _lighten(skin, 40),
                       (hx - int(r * 0.34), hy - int(r * 0.36)), max(1, int(r * 0.32)))
    pygame.draw.circle(surface, _dark(skin, 62), (hx, hy), r, 1)
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
    # hair cap on top; the lower face stays skin (R1: a lit sheen on the crown)
    pygame.draw.circle(surface, hair, (hx, hy - max(1, r // 2)), r)
    pygame.draw.circle(surface, _lighten(hair, 34),
                       (hx - int(r * 0.30), hy - int(r * 0.55)), max(1, int(r * 0.30)))
    if profile:
        pygame.draw.circle(surface, skin,
                           (hx + profile * (r // 3), hy + r // 3),
                           max(1, r * 2 // 3))
        nx = hx + profile * r
        pygame.draw.polygon(surface, skin, [
            (nx, hy - 1), (nx + profile * max(1, r // 3), hy + r // 4),
            (nx, hy + r // 3)])
    else:
        pygame.draw.circle(surface, skin, (hx, hy + r // 3), max(1, r * 2 // 3))
    draw_face(surface, hx, hy, r, expr, profile, blink, look)


def _catchlight(surface, x, y):
    """A 1px specular glint in the eye (bounds-checked)."""
    if 0 <= x < surface.get_width() and 0 <= y < surface.get_height():
        surface.set_at((x, y), (250, 250, 250))


def draw_face(surface, hx, hy, r, expr_name, profile=0, blink=False,
              look=(0.0, 0.0)):
    """G1 the expressive face — brows + eyes (sclera + iris + catchlight, not a
    black void) + a subtle nose + a mouth, all from a 3-param spec (P34.2)."""
    import pygame
    from ui import char_face
    sp = char_face.spec(expr_name)
    ink = (34, 28, 26)
    e = max(1, r // 4)
    ey = hy + r // 5                                # eye row
    sides = (profile,) if profile else (-1, 1)     # one eye in profile
    mode = sp["eyes"]
    lx = int(round(look[0] * r * 0.4))             # pupils lead the look (P34.3)
    ly = int(round(look[1] * r * 0.3))
    for s in sides:
        ex = hx + (s * (r // 3) if not profile else profile * (r // 3))
        px, py = ex + lx, ey + ly                  # pupil position
        if blink or mode == "squint":
            pygame.draw.line(surface, ink, (ex - e, ey), (ex + e, ey), 1)
        elif mode == "wide":
            pygame.draw.circle(surface, (245, 245, 245), (ex, ey), e + 1)
            pygame.draw.circle(surface, ink, (px, py), max(1, e - 1))
            _catchlight(surface, px - 1, py - 1)
        elif mode == "arch":                       # ‿ happy squint
            pygame.draw.arc(surface, ink, (ex - e, ey - e, e * 2, e * 2 + 1),
                            3.4, 6.0, 1)
        elif mode == "x":
            pygame.draw.line(surface, ink, (ex - e, ey - e), (ex + e, ey + e), 1)
            pygame.draw.line(surface, ink, (ex - e, ey + e), (ex + e, ey - e), 1)
        else:                                      # open eye — sclera + iris + glint
            es = max(2, e)
            pygame.draw.ellipse(surface, (247, 245, 238),
                                (ex - es, ey - max(1, es - 1),
                                 es * 2, max(2, (es - 1) * 2)))
            ir = max(1, es - 1)
            pygame.draw.circle(surface, ink, (px, py), ir)
            if es >= 3:
                _catchlight(surface, px - 1, py - 1)
        # brow — inner end nudged by the expression's brow tilt
        bx = ex
        by = ey - max(2, r // 2)
        inner = -s if not profile else -1          # inner = toward centre
        pygame.draw.line(surface, ink,
                         (bx - e, by + inner * sp["brow"] * -1),
                         (bx + e, by - inner * sp["brow"] * -1), 1)
    # nose — a soft 1px shadow between the eyes and the mouth (a little depth),
    # nudged with the gaze; skipped on a very small head where it'd just be noise
    my = hy + r // 2
    if r >= 6:
        nose_ink = (108, 84, 74)
        nx = hx + max(1, r // 9) + int(round(look[0] * r * 0.15))
        n0 = ey + max(1, r // 4)
        n1 = my - max(1, r // 8)
        if n1 > n0:
            pygame.draw.line(surface, nose_ink, (nx, n0), (hx, n1), 1)
    # mouth — an arc curved by the expression (>0 up = smile)
    mc = sp["mouth"]
    mw = max(2, r // 2)
    if abs(mc) < 0.15:
        pygame.draw.line(surface, ink, (hx - mw // 2, my), (hx + mw // 2, my), 1)
    elif mc >= 1.0:                                # open, laughing
        pygame.draw.ellipse(surface, ink, (hx - mw // 2, my - 1, mw, mw // 2 + 2))
    else:
        rect = (hx - mw // 2, my - mw // 2, mw, mw)
        if mc > 0:
            pygame.draw.arc(surface, ink, rect, 3.34, 6.08, 1)   # smile
        else:
            pygame.draw.arc(surface, ink, (hx - mw // 2, my, mw, mw),
                            0.20, 2.94, 1)                        # frown


_BUBBLE_BG = (250, 250, 245)
_BUBBLE_LINE = (60, 55, 50)


def draw_bubble(surface, cx, top_y, kind, r):
    """A small floating symbol bubble above the head (P34.2)."""
    import pygame
    w = max(8, int(r * 2.2))
    bx, by = cx - w // 2, top_y - w - 2
    pygame.draw.circle(surface, _BUBBLE_BG, (cx, by + w // 2), w // 2)
    pygame.draw.circle(surface, _BUBBLE_LINE, (cx, by + w // 2), w // 2, 1)
    pygame.draw.polygon(surface, _BUBBLE_BG,
                        [(cx - 2, by + w - 1), (cx + 2, by + w - 1),
                         (cx, by + w + 3)])
    m, mid = w // 4, by + w // 2
    if kind == "alert":
        pygame.draw.line(surface, (200, 40, 40), (cx, by + m), (cx, mid + 1), 2)
        pygame.draw.circle(surface, (200, 40, 40), (cx, mid + m), 1)
    elif kind == "question":
        pygame.draw.arc(surface, (60, 90, 180),
                        (cx - m, by + m, m * 2, m * 2), 0.4, 3.6, 2)
        pygame.draw.circle(surface, (60, 90, 180), (cx, mid + m), 1)
    elif kind == "sleep":
        for i, s in enumerate((m, m - 1)):
            zx, zy = cx - m + i * 2, by + m + i * 3
            pygame.draw.line(surface, (90, 120, 170), (zx, zy), (zx + s, zy), 1)
            pygame.draw.line(surface, (90, 120, 170),
                             (zx + s, zy), (zx, zy + s), 1)
            pygame.draw.line(surface, (90, 120, 170),
                             (zx, zy + s), (zx + s, zy + s), 1)
    elif kind == "love":
        cr = max(2, w // 6)
        pygame.draw.circle(surface, (210, 60, 90), (cx - cr, mid - 1), cr)
        pygame.draw.circle(surface, (210, 60, 90), (cx + cr, mid - 1), cr)
        pygame.draw.polygon(surface, (210, 60, 90),
                            [(cx - cr * 2, mid), (cx + cr * 2, mid),
                             (cx, mid + cr * 2 + 1)])
    elif kind == "angry":
        for a in (0.6, 2.0, 3.5, 5.0):
            import math
            pygame.draw.line(surface, (200, 60, 40), (cx, mid),
                             (cx + int(m * math.cos(a)), mid + int(m * math.sin(a))), 1)
    elif kind == "note":
        pygame.draw.circle(surface, (70, 60, 120), (cx - 1, mid + m), max(1, m // 2))
        pygame.draw.line(surface, (70, 60, 120),
                         (cx - 1 + m // 2, mid + m), (cx - 1 + m // 2, by + m), 1)


def draw_shield(surface, pose, face, rim, r):
    import pygame
    hx, hy = _pt(pose["l_hand"])
    pygame.draw.circle(surface, face, (hx, hy), r)
    pygame.draw.circle(surface, rim, (hx, hy), r, max(1, r // 4))
    pygame.draw.circle(surface, rim, (hx, hy), max(1, r // 3))


def draw_weapon(surface, weapon, pose, length, w):
    """Draw the weapon from the RIGHT hand, aligned along the forearm. R4: metal
    reads two-tone (a lit edge over a shadowed spine), a blade has a grip + pommel,
    and a staff's orb is a glowing bead — not a flat floating dot."""
    import pygame
    hand = pose["r_hand"]
    elbow = pose["r_elbow"]
    dx, dy = hand[0] - elbow[0], hand[1] - elbow[1]
    d = math.hypot(dx, dy) or 1.0
    ux, uy = dx / d, dy / d                      # forearm direction (out of hand)
    hx, hy = _pt(hand)
    px, py = -uy, ux                             # perpendicular
    if px * _LIGHT[0] + py * _LIGHT[1] < 0:      # ... pointed toward the light
        px, py = -px, -py
    tip = (int(hand[0] + ux * length), int(hand[1] + uy * length))
    steel, wood = (196, 200, 210), (140, 100, 62)
    if weapon in ("sword", "dagger"):
        blade = length if weapon == "sword" else length * 0.55
        tip = (int(hand[0] + ux * blade), int(hand[1] + uy * blade))
        bw = max(2, w)
        pygame.draw.line(surface, _dark(steel, 62), (hx, hy), tip, bw)     # spine
        e = bw * 0.34
        pygame.draw.line(surface, _lighten(steel, 40),                     # lit edge
                         _pt((hx + px * e, hy + py * e)),
                         _pt((tip[0] + px * e, tip[1] + py * e)),
                         max(1, int(bw * 0.42)))
        g = int(blade * 0.18)
        pygame.draw.line(surface, (118, 92, 56),                           # crossguard
                         _pt((hx - px * g, hy - py * g)),
                         _pt((hx + px * g, hy + py * g)), max(2, bw))
        pygame.draw.circle(surface, (150, 116, 60), (hx, hy), max(2, int(bw * 0.7)))
        pygame.draw.circle(surface, (206, 172, 98), (hx, hy), max(1, int(bw * 0.34)))
    elif weapon == "axe":
        pygame.draw.line(surface, wood, (hx, hy), tip, max(2, w))
        b = int(length * 0.30)
        head = [tip, _pt((tip[0] + px * b, tip[1] + py * b)),
                _pt((tip[0] - ux * b, tip[1] - uy * b))]
        pygame.draw.polygon(surface, steel, head)
        pygame.draw.polygon(surface, _lighten(steel, 34), head, 1)         # lit rim
    elif weapon == "mace":
        pygame.draw.line(surface, wood, (hx, hy), tip, max(2, w))
        r = max(2, int(length * 0.2))
        pygame.draw.circle(surface, _dark(steel, 34), tip, r)
        pygame.draw.circle(surface, _lighten(steel, 36),
                           _pt((tip[0] + px * r * 0.4, tip[1] + py * r * 0.4)),
                           max(1, int(r * 0.55)))                           # highlight
    elif weapon == "spear":
        tip = (int(hand[0] + ux * length * 1.4), int(hand[1] + uy * length * 1.4))
        pygame.draw.line(surface, wood, (hx, hy), tip, max(2, w))
        head = [tip, _pt((tip[0] - ux * 5 + px * 3, tip[1] - uy * 5 + py * 3)),
                _pt((tip[0] - ux * 5 - px * 3, tip[1] - uy * 5 - py * 3))]
        pygame.draw.polygon(surface, steel, head)
        pygame.draw.polygon(surface, _lighten(steel, 34), head, 1)
    elif weapon == "staff":
        tip = (int(hand[0] + ux * length * 1.2), int(hand[1] + uy * length * 1.2))
        pygame.draw.line(surface, (120, 86, 52), (hx, hy), tip, max(2, w))
        # a GLOWING bead: a faint aura → a bright core, so it reads magical + fixed
        for rr, cc in ((max(2, int(length * 0.26)), (48, 96, 176)),
                       (max(2, int(length * 0.17)), (108, 172, 250)),
                       (max(1, int(length * 0.09)), (224, 244, 255))):
            pygame.draw.circle(surface, cc, tip, rr)
    elif weapon == "bow":
        r = max(3, int(length * 0.42))
        base = math.atan2(uy, ux)
        rect = (hx - r, hy - r, r * 2, r * 2)
        pygame.draw.arc(surface, (120, 82, 44), rect, base - 1.1, base + 1.1, max(2, w))
        pygame.draw.arc(surface, (176, 128, 74), rect, base - 1.1, base + 1.1,
                        max(1, w // 2))                                     # lit belly
        p1 = (hx + int(r * math.cos(base - 1.1)), hy + int(r * math.sin(base - 1.1)))
        p2 = (hx + int(r * math.cos(base + 1.1)), hy + int(r * math.sin(base + 1.1)))
        pygame.draw.line(surface, (225, 220, 195), p1, p2, 1)
