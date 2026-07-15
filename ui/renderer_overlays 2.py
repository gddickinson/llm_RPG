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


def draw_hp_bar(target, char, x: int, y: int, ts: int) -> None:
    w, h = ts - 4, 3
    ratio = max(0.0, char.hp / max(1, char.max_hp))
    pygame.draw.rect(target, (60, 0, 0), (x + 2, y - 5, w, h))
    pygame.draw.rect(target, (200, 50, 50), (x + 2, y - 5, int(w * ratio), h))
