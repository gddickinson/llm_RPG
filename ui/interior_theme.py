"""P39.2 — interior visual themes (palette + mood per zone).

A zone (building interior or structure level) picks a THEME by keyword in its
name / structure_id — so a tomb reads DARK and DANK, a home WARM, a smithy
SOOTY — from `data/interior_themes.json`. The renderer fills the view with the
theme's `fill`, washes each floor/wall tile with the theme colour, and lays a
faint `mood` overlay over the whole zone. Pure logic + cached tint surfaces.
"""

import logging

import pygame

logger = logging.getLogger("llm_rpg.interior_theme")

_CACHE = {}                     # (key, ts) -> Surface  (tint washes)
_THEMES = None


def _themes() -> dict:
    global _THEMES
    if _THEMES is None:
        try:
            from items.data_loader import load_data_file
            _THEMES = load_data_file("interior_themes.json").get("themes", {})
        except Exception as e:
            logger.debug(f"interior_themes.json: {e}")
            _THEMES = {}
    return _THEMES


def theme_for(zone) -> dict:
    """The theme dict for a zone. Matches keywords in the zone name +
    structure_id; a dungeon (has `rooms`) falls back to 'cave', else 'home'."""
    themes = _themes()
    hay = " ".join(str(getattr(zone, a, "") or "")
                   for a in ("name", "structure_id")).lower()
    for tid, spec in themes.items():
        if any(k in hay for k in spec.get("keywords", [])):
            return spec
    default = "cave" if hasattr(zone, "rooms") else "home"
    return themes.get(default, {})


def fill_color(theme: dict):
    return tuple(theme.get("fill", [18, 14, 10]))


def _shade(c, f):
    return tuple(max(0, min(255, int(v * f))) for v in c[:3])


def tile_surface(theme: dict, kind: str, ts: int):
    """A cached, opaque THEMED floor/wall tile — the material colour (dark dank
    stone for a tomb, warm wood for a home) with a little deterministic texture
    so it isn't dead flat. `kind` is 'floor' or 'wall'. None if the theme has no
    colour for it (caller keeps the base sprite)."""
    rgba = theme.get(kind)
    if not rgba:
        return None
    base = tuple(rgba[:3])
    ck = (f"{kind}:{base}", ts)
    if ck not in _CACHE:
        surf = pygame.Surface((ts, ts))
        surf.fill(base)
        dk, lt = _shade(base, 0.82), _shade(base, 1.14)
        step = max(4, ts // 6)
        for gy in range(0, ts, step):           # faint block texture
            for gx in range(0, ts, step):
                if (gx // step + gy // step) % 2:
                    surf.fill(dk, (gx, gy, step - 1, step - 1))
        if kind == "wall":                       # a mortar line + top highlight
            pygame.draw.line(surf, dk, (0, ts // 2), (ts, ts // 2), 1)
            pygame.draw.line(surf, lt, (0, 0), (ts, 0), 1)
        _CACHE[ck] = surf
    return _CACHE[ck]


def mood_overlay(theme: dict, w: int, h: int):
    """A faint full-view mood tint (cached by size + colour)."""
    rgba = theme.get("mood")
    if not rgba:
        return None
    ck = (f"mood:{rgba}", w, h)
    if ck not in _CACHE:
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        surf.fill(tuple(rgba))
        _CACHE[ck] = surf
    return _CACHE[ck]
