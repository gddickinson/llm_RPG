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


def _atk_hurt(a):
    """(attack, hurt) progress 0..1 from the shared anim state (P34.24)."""
    atk_t = a.get("atk_t", 0.0)
    attack = 1.0 - atk_t / 0.32 if atk_t > 0 else 0.0
    hurt = 0.0
    if a.get("cur_action") == "hurt" and a.get("action_dur"):
        hurt = 1.0 - a.get("action_t", 0.0) / a["action_dur"]
    return max(0.0, min(1.0, attack)), max(0.0, min(1.0, hurt))


def draw_creature(surface, char, sx, sy, tile_size, plan, is_player=False):
    if not PYGAME_OK:
        return
    if plan == "quadruped":
        _draw_quadruped(surface, char, sx, sy, tile_size)
    elif plan == "slime":
        _draw_slime(surface, char, sx, sy, tile_size)
    elif plan == "wisp":
        _draw_wisp(surface, char, sx, sy, tile_size)
    elif plan == "avian":
        _draw_avian(surface, char, sx, sy, tile_size)
    elif plan == "arachnid":
        _draw_arachnid(surface, char, sx, sy, tile_size)
    _health_bar(surface, char, sx, sy, tile_size)
    from ui import char_fx                          # P34.19 fire / wet on beasts too
    char_fx.draw_effects(surface, char, sx, sy, tile_size,
                         _anim(char).get("clock", 0.0))


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
    attack, hurt = _atk_hurt(a)
    p = creature_pose.quadruped_points(cx, foot_y, size, walk, face,
                                       a.get("moving", False), attack=attack,
                                       hurt=hurt)
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
    attack, hurt = _atk_hurt(a)
    cx = sx + tile_size / 2.0
    base_y = sy + tile_size - 2
    # rears up tall & narrow to POUNCE, squashes wide & low when HURT (P34.24)
    w = tile_size * (0.62 + 0.06 * math.sin(t) - attack * 0.12 + hurt * 0.10)
    h = tile_size * (0.5 - 0.05 * math.sin(t) + attack * 0.20 - hurt * 0.08)
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


_AVIAN_COLOR = {"raven": (54, 54, 66), "crow": (48, 48, 58), "bat": (70, 60, 66),
                "owl": (150, 130, 100), "hawk": (140, 110, 80),
                "pheasant": (170, 120, 70), "eagle": (110, 92, 74),
                "imp": (150, 70, 70), "wyvern": (90, 110, 90)}


def _draw_avian(surface, char, sx, sy, tile_size):
    """A flyer — a small body that hovers/bobs with two flapping wings + a beak."""
    a = _anim(char)
    t = a.get("idle_phase", 0.0) + a.get("walk_phase", 0.0)
    attack, hurt = _atk_hurt(a)
    color = _pick(char, _AVIAN_COLOR, (90, 90, 104))
    cx = sx + tile_size / 2.0
    cy = sy + tile_size * 0.45 - math.sin(t * 2) * tile_size * 0.06     # hovers
    flap = math.sin(t * 8)                                              # wing-beat
    span = tile_size * (0.42 + attack * 0.1)
    for side in (-1, 1):                                                # two wings
        tip = (cx + side * span, cy - flap * tile_size * 0.22)
        mid = (cx + side * span * 0.5, cy + tile_size * 0.02 - flap * tile_size * 0.1)
        pygame.draw.polygon(surface, color, [
            (int(cx), int(cy)), (int(mid[0]), int(mid[1])),
            (int(tip[0]), int(tip[1]))])
        pygame.draw.polygon(surface, _dark(color, 30), [
            (int(cx), int(cy)), (int(mid[0]), int(mid[1])),
            (int(tip[0]), int(tip[1]))], 1)
    br = int(tile_size * 0.16)
    pygame.draw.circle(surface, color, (int(cx), int(cy)), br)         # body
    hr = int(tile_size * 0.10)
    hy = int(cy - br * 0.6)
    pygame.draw.circle(surface, color, (int(cx), hy), hr)              # head
    pygame.draw.polygon(surface, (230, 190, 80), [                     # beak
        (int(cx + hr), hy), (int(cx + hr + tile_size * 0.08), hy + 1),
        (int(cx + hr), hy + hr // 2)])
    pygame.draw.circle(surface, (20, 20, 24), (int(cx + hr // 2), hy - 1),
                       max(1, hr // 3))
    # tail
    pygame.draw.polygon(surface, _dark(color, 12), [
        (int(cx), int(cy + br)), (int(cx - tile_size * 0.1), int(cy + br * 1.6)),
        (int(cx + tile_size * 0.04), int(cy + br * 1.3))])


def _draw_arachnid(surface, char, sx, sy, tile_size):
    """A spider — a round abdomen + eight bent, skittering legs."""
    a = _anim(char)
    t = a.get("idle_phase", 0.0) + a.get("walk_phase", 0.0)
    attack, hurt = _atk_hurt(a)
    color = (60, 52, 60) if "spider" in _species(char) else (90, 76, 54)
    cx = sx + tile_size / 2.0
    cy = sy + tile_size * 0.62 - hurt * tile_size * 0.08
    abd = int(tile_size * 0.22)
    lw = max(2, int(tile_size * 0.05))
    for i in range(8):                                                 # 8 legs
        side = -1 if i < 4 else 1
        row = i % 4
        skit = math.sin(t * 6 + i) * tile_size * 0.05
        base = (cx + side * abd * 0.5, cy)
        knee = (base[0] + side * tile_size * (0.22 + 0.03 * (row - 1.5)),
                cy - tile_size * 0.12 + skit)
        foot = (knee[0] + side * tile_size * 0.14,
                cy + tile_size * 0.16 + (row - 1.5) * tile_size * 0.06)
        pygame.draw.line(surface, _dark(color, 20), base, knee, lw)
        pygame.draw.line(surface, _dark(color, 20), knee, foot, lw)
    lunge = attack * tile_size * 0.12
    pygame.draw.ellipse(surface, color,                                # abdomen
                        (int(cx - abd), int(cy - abd * 0.7),
                         int(abd * 2), int(abd * 1.5)))
    hr = int(tile_size * 0.11)
    hx = int(cx + abd * 0.7 + lunge)
    pygame.draw.circle(surface, _dark(color, 12), (hx, int(cy)), hr)   # head
    for ex in (-1, 1):                                                 # eyes
        pygame.draw.circle(surface, (200, 60, 60),
                           (hx + hr // 2, int(cy) + ex * hr // 2), max(1, hr // 4))


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
