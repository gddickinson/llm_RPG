"""Death popup — the centered Restart / Quit overlay shown when the player
has been defeated. Split out of `ui/gui.py` to hold the 500-line line;
pure rendering over the GUI's screen + fonts.
"""

try:
    import pygame
    PYGAME_OK = True
except ImportError:  # pragma: no cover
    PYGAME_OK = False


def draw_death_popup(gui) -> None:
    """Centered popup with Restart / Quit options over the dimmed world."""
    if not PYGAME_OK:
        return
    screen = gui.screen
    hud = gui.hud
    screen_rect = screen.get_rect()
    veil = pygame.Surface(screen_rect.size, pygame.SRCALPHA)
    veil.fill((0, 0, 0, 170))
    screen.blit(veil, (0, 0))

    w, h = 460, 220
    box = pygame.Rect((screen_rect.width - w) // 2,
                      (screen_rect.height - h) // 2, w, h)
    pygame.draw.rect(screen, (25, 10, 12), box)
    pygame.draw.rect(screen, (200, 60, 60), box, 3)

    def _center(surf, y):
        screen.blit(surf, (box.centerx - surf.get_width() // 2, y))

    if hud.big_font:
        _center(hud.big_font.render("You have been defeated!", True,
                                    (255, 90, 90)), box.y + 28)
    if hud.font:
        xp = (gui.engine.player.metadata or {}).get("xp", 0)
        level = gui.engine.player.level
        _center(hud.font.render(
            f"Final level: {level}    XP: {xp}    "
            f"Turn: {gui.engine.turn_counter}", True, (220, 220, 220)),
            box.y + 72)
        _center(hud.font.render("[R] Restart", True, (160, 230, 160)),
                box.y + 120)
        _center(hud.font.render("[Q] Quit", True, (230, 160, 160)),
                box.y + 150)
        _center(hud.font.render("(or press ESC to quit)", True,
                                (160, 160, 180)), box.y + 184)
