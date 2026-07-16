"""Settings overlay (PUX.4a) — the in-game options menu.

Lists the `engine/settings.py` options with their current value.
Up/Down picks a row, Left/Right (or Enter) cycles that option's value,
Esc or ',' closes. Cycling a value both persists it (the model) and
applies its live effect through `apply_setting` — map zoom re-sizes the
renderer, Sound mutes the SFX; the on/off gates (hint bar, mini-map)
and the log-detail level are read straight off the settings each frame
by the HUD and the event filter, so they need no explicit apply.
"""

import logging

from engine import settings

try:
    import pygame
    PYGAME_OK = True
except ImportError:  # pragma: no cover
    PYGAME_OK = False

logger = logging.getLogger("llm_rpg.settings_panel")


def init_zoom(gui) -> None:
    """ISO.10: sync the live tile size to the player's saved / default map-zoom
    setting at startup — not only when the settings overlay is opened, so the
    chosen zoom (and the bigger new default) applies from boot."""
    try:
        from engine import settings
        z = settings.get_setting(gui.engine.player, "zoom")
        if isinstance(z, int) and z > 0:
            apply_setting(gui, "zoom", z)
    except Exception:
        pass


def apply_setting(gui, key, value) -> None:
    """Push a changed setting into the live GUI where it needs it."""
    if key == "zoom":
        gui.tile_size = value
        gui.renderer.tile_size = value
        try:
            gui.renderer.sprites.tile_size = value
            gui.renderer.sprites._tile_cache.clear()
            gui.renderer.sprites._char_cache.clear()
        except Exception:
            pass
    elif key == "sound":
        try:
            gui.sound.enabled = (value == "on")
        except Exception:
            pass
    elif key == "autoplay":            # M.3: hand the hero to an agent
        try:
            gui.engine.roster.set_away(gui.engine.player, value == "on")
        except Exception:
            pass


class SettingsPanel:
    def __init__(self, gui):
        self.gui = gui
        self.engine = gui.engine
        self.cursor = 0
        self._font = None
        self._big = None

    def _ensure_font(self):
        if self._font is None and PYGAME_OK:
            pygame.font.init()
            self._font = pygame.font.SysFont("monospace", 16)
            self._big = pygame.font.SysFont("monospace", 20, bold=True)

    # ---------------- input -----------------------------------------

    def handle_key(self, event) -> bool:
        if event.type != pygame.KEYDOWN:
            return True
        k = event.key
        opts = settings.all_options()
        if k in (pygame.K_UP, pygame.K_w):
            self.cursor = (self.cursor - 1) % len(opts)
        elif k in (pygame.K_DOWN, pygame.K_s):
            self.cursor = (self.cursor + 1) % len(opts)
        elif k in (pygame.K_LEFT, pygame.K_a):
            self._cycle(-1)
        elif k in (pygame.K_RIGHT, pygame.K_d,
                   pygame.K_RETURN, pygame.K_SPACE):
            self._cycle(1)
        elif k in (pygame.K_ESCAPE, pygame.K_COMMA):
            self.gui.mode = "play"
        return True

    def _cycle(self, step: int) -> None:
        opt = settings.all_options()[self.cursor]
        val = settings.cycle_setting(self.engine.player, opt["key"], step)
        apply_setting(self.gui, opt["key"], val)

    # ---------------- render ----------------------------------------

    def draw(self, target, screen_rect) -> None:
        if not PYGAME_OK:
            return
        self._ensure_font()
        w = min(screen_rect.width - 80, 520)
        h = min(screen_rect.height - 80, 360)
        box = pygame.Rect((screen_rect.width - w) // 2,
                          (screen_rect.height - h) // 2, w, h)
        s = pygame.Surface(box.size, pygame.SRCALPHA)
        s.fill((10, 10, 20, 240))
        target.blit(s, box.topleft)
        pygame.draw.rect(target, (200, 180, 100), box, 2)
        target.blit(self._big.render("Settings", True, (255, 220, 120)),
                    (box.x + 16, box.y + 12))

        y = box.y + 54
        opts = settings.all_options()
        for i, opt in enumerate(opts):
            val = settings.get_setting(self.engine.player, opt["key"])
            sel = (i == self.cursor)
            color = (255, 240, 160) if sel else (215, 215, 225)
            prefix = "> " if sel else "  "
            label = self._font.render(f"{prefix}{opt['label']}", True,
                                      color)
            target.blit(label, (box.x + 20, y))
            arrows = f"< {val} >" if sel else f"{val}"
            v = self._font.render(arrows, True, color)
            target.blit(v, (box.right - 20 - v.get_width(), y))
            y += 28

        hint = self._font.render(
            "[↕] pick   [↔ / Enter] change   [, / Esc] close",
            True, (160, 160, 180))
        target.blit(hint, (box.x + 16, box.bottom - 28))
