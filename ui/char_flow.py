"""P34.5 hair / cloak / weapon-trail flow — real secondary motion.

A verlet CHAIN (pure) pinned to the head (hair/ponytail) and, for robed classes,
the shoulders (a billowing cloak) lags the body, hangs under gravity and sways —
so movement gains flow. A fading weapon-swing TRAIL smears an arc behind a strike.

Everything runs in BODY-LOCAL space (offsets from a static tile anchor), exactly
like the P34.3 springs, so a camera pan or a jump between locations never smears
it. The pure integrators are headless-testable; the thin pygame draw is lazy.
"""

import math

try:
    import pygame
    PYGAME_OK = True
except ImportError:                                     # pragma: no cover
    PYGAME_OK = False

# robed / caped callings get a cloak
CLOAK_CLASSES = {"wizard", "sorcerer", "warlock", "cleric", "druid", "rogue",
                 "noble", "ranger", "bard", "monk", "paladin"}
TRAIL_MAX = 6


# ------------------------------------------------------------- pure physics

def init_chain(rx, ry, n, seg):
    """A chain of `n` verlet nodes hanging straight down from the root."""
    return [[rx, ry + seg * (i + 1), rx, ry + seg * (i + 1)] for i in range(n)]


def step_chain(nodes, rx, ry, seg, gravity, damp, wind):
    """One verlet step: integrate velocity + gravity + wind, then pin each node
    `seg` from its parent (root for the first). Mutates & returns `nodes`."""
    for nd in nodes:
        vx = (nd[0] - nd[2]) * damp
        vy = (nd[1] - nd[3]) * damp
        nd[2], nd[3] = nd[0], nd[1]
        nd[0] += vx + wind
        nd[1] += vy + gravity
    px, py = rx, ry
    for nd in nodes:
        dx, dy = nd[0] - px, nd[1] - py
        d = math.hypot(dx, dy) or 1.0
        nd[0] = px + dx / d * seg
        nd[1] = py + dy / d * seg
        px, py = nd[0], nd[1]
    return nodes


def push_trail(trail, x, y):
    """Record a weapon-tip point for the swing trail (capped, oldest dropped)."""
    trail.append([x, y])
    if len(trail) > TRAIL_MAX:
        del trail[0]
    return trail


# ------------------------------------------------------------- thin drawing

def _anchor(sx, sy, ts):
    return sx + ts / 2.0, sy + ts - 2.0


def draw_back(surface, char, anim, pose, sx, sy, ts, H, hair_color, cloak_color):
    """Integrate + draw the flow layers that sit BEHIND the body: the cloak, then
    the hair. Call before the limbs are drawn."""
    if not PYGAME_OK:
        return
    ax, ay = _anchor(sx, sy, ts)
    sec = anim.setdefault("_sec", {})
    clock = anim.get("clock", 0.0)
    wind = math.sin(clock * 1.5) * H * 0.006
    grav, damp = H * 0.03, 0.86
    # cloak (robed classes) — a wider, slower chain from the upper back
    if cloak_color is not None:
        nx = (pose["neck"][0] - ax, pose["neck"][1] - ay + H * 0.02)
        seg = H * 0.14
        nodes = sec.get("cloak") or init_chain(nx[0], nx[1], 3, seg)
        step_chain(nodes, nx[0], nx[1], seg, grav * 1.1, 0.90, wind * 1.4)
        sec["cloak"] = nodes
        _blit_cloak(surface, ax, ay, pose, nodes, cloak_color, H)
    # hair / ponytail — a light chain off the BACK-TOP of the head that trails
    # behind (low gravity + a backward bias) so it flows rather than dropping
    fdir = pose.get("fdir", 0) or 0
    hr = pose.get("head_r", H * 0.14)
    hx = pose["head"][0] - ax - fdir * hr * 0.6
    hy = pose["head"][1] - ay - hr * 0.4
    seg = H * 0.075
    nodes = sec.get("hair") or init_chain(hx, hy, 3, seg)
    step_chain(nodes, hx, hy, seg, H * 0.014, 0.88, wind - fdir * H * 0.012)
    sec["hair"] = nodes
    _blit_hair(surface, ax, ay, (hx, hy), nodes, hair_color, H)


def draw_front(surface, anim, pose, sx, sy, ts, atk_t, weapon):
    """The weapon-swing TRAIL — a fading arc behind the weapon. Call after the
    body + weapon are drawn (it sits in front)."""
    if not PYGAME_OK or not weapon:
        return
    ax, ay = _anchor(sx, sy, ts)
    sec = anim.setdefault("_sec", {})
    trail = sec.get("trail") or []
    if atk_t > 0:                                       # mid-swing: extend the arc
        hx, hy = pose["r_hand"][0] - ax, pose["r_hand"][1] - ay
        push_trail(trail, hx, hy)
    elif trail:                                         # swing over: let it fade
        del trail[0]
    sec["trail"] = trail
    if len(trail) >= 2:
        _blit_trail(surface, ax, ay, trail)


def _blit_hair(surface, ax, ay, root, nodes, color, H):
    pts = [(ax + root[0], ay + root[1])] + [(ax + n[0], ay + n[1]) for n in nodes]
    w = max(2, int(H * 0.10))
    for i in range(len(pts) - 1):
        pygame.draw.line(surface, color, pts[i], pts[i + 1],
                         max(1, int(w * (1 - i / len(pts)))))
    pygame.draw.circle(surface, color, (int(pts[-1][0]), int(pts[-1][1])),
                       max(1, w // 3))


def _blit_cloak(surface, ax, ay, pose, nodes, color, H):
    l_sh = (pose["l_sh"][0], pose["l_sh"][1] + H * 0.02)
    r_sh = (pose["r_sh"][0], pose["r_sh"][1] + H * 0.02)
    spread = H * 0.16
    mid = (ax + nodes[1][0], ay + nodes[1][1])
    tip = (ax + nodes[-1][0], ay + nodes[-1][1])
    poly = [l_sh, r_sh,
            (mid[0] + spread, mid[1]), (tip[0] + spread * 0.6, tip[1]),
            (tip[0] - spread * 0.6, tip[1]), (mid[0] - spread, mid[1])]
    pygame.draw.polygon(surface, color, poly)
    pygame.draw.polygon(surface, tuple(max(0, c - 25) for c in color), poly, 1)


def _blit_trail(surface, ax, ay, trail):
    n = len(trail)
    for i in range(n - 1):
        a, b = trail[i], trail[i + 1]
        alpha = int(210 * (i + 1) / n)
        w = max(2, int(9 * (i + 1) / n))
        seg = pygame.Surface((abs(a[0] - b[0]) + w * 2 + 2,
                              abs(a[1] - b[1]) + w * 2 + 2), pygame.SRCALPHA)
        ox, oy = min(a[0], b[0]) - w, min(a[1], b[1]) - w
        pygame.draw.line(seg, (220, 230, 255, alpha),
                         (a[0] - ox, a[1] - oy), (b[0] - ox, b[1] - oy), w)
        surface.blit(seg, (ax + ox, ay + oy))
