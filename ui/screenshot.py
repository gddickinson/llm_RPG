"""In-game SCREENSHOT capture (George: build screenshots into the GUI).

`F12` in any mode saves the current frame to `screenshots/` at the project
root (override with `LLM_RPG_SCREENSHOT_DIR`). The filename carries the
in-game context — hero, level, day — so a soak-test session's shots are
self-describing. Pure enough to call from a headless harness (it just
needs a `gui.screen` surface).
"""

import logging
import os
import re

logger = logging.getLogger("llm_rpg.screenshot")

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def screenshot_dir() -> str:
    d = os.environ.get("LLM_RPG_SCREENSHOT_DIR") \
        or os.path.join(_ROOT, "screenshots")
    try:
        os.makedirs(d, exist_ok=True)
    except Exception:
        pass
    return d


def _slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", str(text)).strip("-").lower() or "x"


def _context(engine) -> str:
    """A short, filesystem-safe tag from the current game state."""
    try:
        p = engine.player
        lvl = getattr(p, "level", 1)
        day = getattr(getattr(engine.world, "calendar", None), "day", None) \
            if hasattr(engine, "world") else None
        bits = [_slug(getattr(p, "name", "hero")), f"lv{lvl}"]
        if day is not None:
            bits.append(f"d{day}")
        return "_".join(bits)
    except Exception:
        return "game"


def save_screenshot(gui, tag: str = "") -> str:
    """Save `gui.screen` to a uniquely-named PNG; returns the path (or "")."""
    import pygame
    surf = getattr(gui, "screen", None)
    if surf is None:
        return ""
    engine = getattr(gui, "engine", None)
    ctx = _context(engine) if engine is not None else "game"
    # a monotonically increasing index keeps names unique + ordered without
    # needing a wall-clock (headless soak tests fire many per second)
    d = screenshot_dir()
    idx = 0
    try:
        existing = [f for f in os.listdir(d) if f.startswith("shot_")]
        idx = len(existing)
    except Exception:
        pass
    name = f"shot_{idx:04d}_{ctx}"
    if tag:
        name += "_" + _slug(tag)
    name += ".png"
    path = os.path.join(d, name)
    try:
        pygame.image.save(surf, path)
    except Exception as e:
        logger.warning(f"screenshot failed: {e}")
        return ""
    if engine is not None:
        try:
            engine.memory_manager.add_event(f"[Shot] saved {name}")
        except Exception:
            pass
    return path
