"""Small map-overlay draw helpers split out of `renderer.py` to hold the
500-line line: the pet critter marker and the over-head HP bar."""

import pygame


def draw_pet(target, pet: dict, x: int, y: int, ts: int) -> None:
    """A tiny bobbing critter: coloured body + eyes."""
    color = tuple(pet.get("color", (200, 200, 200)))
    cx = x + ts // 2
    cy = y + int(ts * 0.68)
    r = max(3, ts // 5)
    pygame.draw.circle(target, color, (cx, cy), r)
    dark = tuple(max(0, c - 70) for c in color)
    pygame.draw.circle(target, dark, (cx, cy), r, 1)
    eye = max(1, ts // 20)
    pygame.draw.circle(target, (20, 20, 25), (cx - r // 2, cy - eye), eye)
    pygame.draw.circle(target, (20, 20, 25), (cx + r // 2, cy - eye), eye)


_MOUNT_HIDE = {"horse": (128, 86, 54), "war_horse": (92, 76, 68),
               "mule": (122, 110, 98), "donkey": (150, 140, 126),
               "elephant": (144, 144, 152), "magic_carpet": (150, 60, 70)}


def draw_mount(target, kind: str, x: int, y: int, ts: int) -> None:
    """A trailing mount (P28.2d): a baked Quaternius GLB model where we have one
    for this kind (#9 — horse/war-horse/mule/donkey), else a simple four-legged
    silhouette. `x, y` is the tile's top-left; the beast stands in its lower half."""
    try:
        from ui import creature_glb
        spr = creature_glb.sprite(kind, int(ts * 1.5))
        if spr is not None:
            w, h = spr.get_size()
            cx = x + ts // 2
            ground_y = y + int(ts * 0.94)          # where the procedural legs end
            target.blit(spr, (cx - w // 2, ground_y - int(h * 0.62)))
            return
    except Exception:
        pass
    hide = _MOUNT_HIDE.get(kind, (128, 96, 64))
    dark = tuple(max(0, c - 48) for c in hide)
    cx = x + ts // 2
    by = y + int(ts * 0.70)
    bw, bh = int(ts * 0.62), int(ts * 0.30)
    leg = max(2, ts // 15)
    for lx in (cx - bw // 3, cx - bw // 8, cx + bw // 8, cx + bw // 3):
        pygame.draw.line(target, dark, (lx, by),
                         (lx, by + int(ts * 0.24)), leg)
    pygame.draw.ellipse(target, hide, (cx - bw // 2, by - bh, bw, bh))
    # neck + head toward the front (left)
    hx, hy = cx - bw // 2, by - bh // 2
    nx, ny = hx - int(ts * 0.12), by - int(ts * 0.42)
    pygame.draw.line(target, hide, (hx, hy), (nx, ny), max(2, ts // 9))
    pygame.draw.circle(target, hide, (nx, ny), max(2, ts // 8))
    pygame.draw.circle(target, dark, (nx, ny), max(2, ts // 8), 1)


def draw_hp_bar(target, char, x: int, y: int, ts: int) -> None:
    w, h = ts - 4, 3
    ratio = max(0.0, char.hp / max(1, char.max_hp))
    pygame.draw.rect(target, (60, 0, 0), (x + 2, y - 5, w, h))
    pygame.draw.rect(target, (200, 50, 50), (x + 2, y - 5, int(w * ratio), h))
