"""P34.18 creature drawing (thin pygame over `creature_pose`).

Draws the non-humanoid body plans — a four-legged beast (legs depth-sorted so the
far pair sits behind the body), a wobbling slime, a bobbing wisp — each animated
from the shared `_anim` state. Colours come from the species. `body_renderer`
dispatches here when `creature_pose.body_plan` isn't "humanoid".
"""

import math

try:
    import pygame
    PYGAME_OK = True
except ImportError:                                    # pragma: no cover
    PYGAME_OK = False

from ui import creature_pose

# species → (body, belly/under) fur colours
_FUR = {
    "wolf": ((110, 112, 120), (150, 150, 158)), "direwolf": ((90, 92, 104), (130, 130, 140)),
    "warg": ((90, 80, 84), (120, 110, 112)),
    "fox": ((196, 108, 54), (232, 212, 190)), "boar": ((92, 74, 60), (120, 104, 90)),
    "hog": ((120, 96, 78), (150, 130, 112)), "bear": ((96, 74, 56), (120, 100, 82)),
    "deer": ((162, 122, 82), (214, 194, 168)), "stag": ((150, 112, 74), (206, 186, 160)),
    "rabbit": ((178, 168, 156), (232, 228, 222)), "hare": ((160, 142, 120), (220, 210, 198)),
    "cat": ((120, 110, 100), (170, 162, 152)), "lynx": ((172, 150, 120), (216, 204, 186)),
    "horse": ((110, 82, 60), (150, 120, 96)), "pony": ((120, 92, 68), (160, 132, 104)),
    "mule": ((122, 110, 96), (158, 148, 136)), "goat": ((150, 142, 130), (196, 190, 180)),
}
_SLIME_COLOR = {"slime": (110, 190, 120), "ooze": (120, 160, 90),
                "jelly": (150, 120, 200), "blob": (150, 180, 130)}
_WISP_COLOR = {"wisp": (140, 220, 210), "flame": (240, 160, 70),
               "ember": (240, 120, 60), "ghost": (180, 200, 230),
               "wraith": (150, 140, 180), "lurker": (110, 150, 120)}


def _species(char):
    return ((getattr(char, "name", "") or "") + " " +
            str(getattr(char, "id", ""))).lower()


def _pick(char, table, default):
    sp = _species(char)
    for key, val in table.items():
        if key in sp:
            return val
    return default


def _anim(char):
    return (getattr(char, "metadata", None) or {}).get("_anim", {}) or {}


def draw_creature(surface, char, sx, sy, tile_size, plan, is_player=False):
    if not PYGAME_OK:
        return
    if plan == "quadruped":
        _draw_quadruped(surface, char, sx, sy, tile_size)
    elif plan == "slime":
        _draw_slime(surface, char, sx, sy, tile_size)
    elif plan == "wisp":
        _draw_wisp(surface, char, sx, sy, tile_size)
    _health_bar(surface, char, sx, sy, tile_size)


def _dark(c, a=28):
    return tuple(max(0, x - a) for x in c)


def _draw_quadruped(surface, char, sx, sy, tile_size):
    a = _anim(char)
    size = tile_size * 1.2
    cx = sx + tile_size / 2.0
    foot_y = sy + tile_size - 2
    walk = a.get("walk_phase", 0.0) if a.get("moving") else a.get("idle_phase", 0.0)
    face = a.get("face_cur", 90.0)
    body, belly = _pick(char, _FUR, ((120, 112, 104), (156, 150, 142)))
    pointy = any(k in _species(char) for k in ("wolf", "fox", "warg", "cat",
                                               "lynx", "hound", "dog"))
    p = creature_pose.quadruped_points(cx, foot_y, size, walk, face,
                                       a.get("moving", False))
    # shadow
    shw = int(size * 0.5)
    sh = pygame.Surface((shw, max(2, shw // 3)), pygame.SRCALPHA)
    pygame.draw.ellipse(sh, (0, 0, 0, 90), sh.get_rect())
    surface.blit(sh, (int(cx - shw / 2), int(foot_y - shw // 6)))
    lw = max(2, int(size * 0.07))
    legs = sorted(p["legs"].values(), key=lambda L: L[2])   # far first
    for i, (hip, foot, depth) in enumerate(legs):
        col = _dark(body, 40) if i < 2 else _dark(body, 15)
        pygame.draw.line(surface, col, hip, foot, lw)
        pygame.draw.circle(surface, _dark(col, 20),
                           (int(foot[0]), int(foot[1])), max(1, lw // 2))
    # tail
    pygame.draw.line(surface, _dark(body, 10), p["tail_root"], p["tail_tip"],
                     max(2, int(size * 0.06)))
    # body — a rounded blob between shoulder and hip
    br = int(size * 0.24)
    _blob(surface, p["shoulder"], p["hip"], br, body, belly)
    # head + snout + ears
    hr = int(size * 0.16)
    hx, hy = int(p["head"][0]), int(p["head"][1])
    pygame.draw.line(surface, body, p["head"], p["snout"], int(hr * 1.1))
    pygame.draw.circle(surface, body, (hx, hy), hr)
    pygame.draw.circle(surface, _dark(body, 22), (hx, hy), hr, 1)
    if pointy:
        for ex, ey in (p["ear1"], p["ear2"]):
            pygame.draw.polygon(surface, body, [
                (hx, hy - hr // 2), (int(ex), int(ey)),
                (hx + hr // 3, hy - hr // 2)])
    # snout tip + an eye
    sxp, syp = int(p["snout"][0]), int(p["snout"][1])
    pygame.draw.circle(surface, _dark(body, 45), (sxp, syp), max(1, hr // 3))
    pygame.draw.circle(surface, (20, 20, 24), (hx + hr // 3, hy - hr // 4),
                       max(1, hr // 4))


def _blob(surface, a, b, r, color, belly):
    mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
    rect = pygame.Rect(0, 0, int(abs(a[0] - b[0]) + r * 2), int(r * 1.7))
    rect.center = (int(mx), int(my))
    pygame.draw.ellipse(surface, color, rect)
    pygame.draw.ellipse(surface, _dark(color, 30), rect, 1)
    br = rect.inflate(-r, -int(r * 0.7))
    br.centery += int(r * 0.4)
    pygame.draw.ellipse(surface, belly, br)


def _draw_slime(surface, char, sx, sy, tile_size):
    a = _anim(char)
    t = a.get("idle_phase", 0.0) + a.get("walk_phase", 0.0)
    color = _pick(char, _SLIME_COLOR, (120, 180, 120))
    cx = sx + tile_size / 2.0
    base_y = sy + tile_size - 2
    w = tile_size * (0.62 + 0.06 * math.sin(t))        # wobble wide/narrow
    h = tile_size * (0.5 - 0.05 * math.sin(t))
    rect = pygame.Rect(0, 0, int(w), int(h * 1.6))
    rect.midbottom = (int(cx), int(base_y))
    pygame.draw.ellipse(surface, color, rect)
    pygame.draw.ellipse(surface, _dark(color, 30), rect, 1)
    hi = rect.inflate(-int(w * 0.5), -int(h))
    hi.centery = rect.top + int(h * 0.5)
    pygame.draw.ellipse(surface, tuple(min(255, x + 40) for x in color), hi)
    for ex in (-1, 1):                                  # two dark eyes
        pygame.draw.circle(surface, (20, 30, 20),
                           (int(cx + ex * w * 0.18), rect.centery), max(1, int(w * 0.06)))


def _draw_wisp(surface, char, sx, sy, tile_size):
    a = _anim(char)
    t = a.get("idle_phase", 0.0) + a.get("walk_phase", 0.0)
    color = _pick(char, _WISP_COLOR, (150, 210, 210))
    cx = sx + tile_size / 2.0 + math.sin(t) * tile_size * 0.06
    cy = sy + tile_size * 0.45 - abs(math.sin(t * 1.3)) * tile_size * 0.12
    for i, rad in enumerate((0.34, 0.24, 0.15)):        # a soft glowing core
        r = int(tile_size * rad)
        glow = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        alpha = 70 + i * 60
        pygame.draw.circle(glow, (*color, alpha), (r, r), r)
        surface.blit(glow, (int(cx - r), int(cy - r)))
    # trailing sparks
    for k in range(3):
        px = cx - math.sin(t + k) * tile_size * 0.1
        py = cy + k * tile_size * 0.12
        pygame.draw.circle(surface, color, (int(px), int(py)), max(1, tile_size // 16))


def _health_bar(surface, char, sx, sy, tile_size):
    try:
        if getattr(char, "max_hp", 0) > 0 and char.hp < char.max_hp:
            bw = int(tile_size * 0.6)
            bx = int(sx + tile_size / 2 - bw / 2)
            by = int(sy + tile_size * 0.10)
            pygame.draw.rect(surface, (60, 0, 0), (bx, by, bw, 3))
            pygame.draw.rect(surface, (200, 60, 60),
                             (bx, by, int(bw * max(0.0, char.hp / char.max_hp)), 3))
    except Exception:
        pass
