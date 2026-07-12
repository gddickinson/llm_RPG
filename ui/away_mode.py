"""Absent-player heartbeat (M.3) — while the active hero's human is
away, the game normally freezes (only player actions advance the
world). This ticks the world on a slow cadence so the agent driving
the away hero (via `drive_agents` in the turn pipeline) keeps it, and
the world, alive until the human returns. Any keypress hands back.
"""

HEARTBEAT_FRAMES = 15        # ~0.5s at 30fps between auto-ticks

BANNER = ("◆ AUTOPLAY — the agent has your hero  "
          "·  move or act to take control")

try:
    import pygame
    # Keys that OBSERVE without taking the reins — you press these to CHECK
    # ON autoplay (open settings, a journal, the map, help, save/load), not
    # to end it. Everything else — movement and actions — hands control
    # back. Bug-fix 2026-07-12d: the old 'any key hands back' meant opening
    # the settings overlay to confirm autoplay silently switched it OFF, so
    # it 'never worked'.
    _OBSERVE_KEYS = frozenset({
        pygame.K_COMMA, pygame.K_F1, pygame.K_F11, pygame.K_F5, pygame.K_F9,
        pygame.K_i, pygame.K_c, pygame.K_q, pygame.K_o, pygame.K_j,
        pygame.K_u, pygame.K_y, pygame.K_l, pygame.K_ESCAPE,
        pygame.K_SLASH, pygame.K_QUESTION,
    })
except Exception:                       # headless without pygame
    pygame = None
    _OBSERVE_KEYS = frozenset()


def hands_back(engine, event) -> bool:
    """True if this keypress should return control to the human: a key that
    DIRECTS the hero (move/attack/act) while the hero is agent-driven. An
    observe/panel/system key never ends autoplay."""
    if pygame is None or getattr(event, "type", None) != pygame.KEYDOWN:
        return False
    if getattr(event, "key", None) in _OBSERVE_KEYS:
        return False
    try:
        return bool(engine.roster.is_away(engine.player))
    except Exception:
        return False


def heartbeat(gui) -> None:
    try:
        if not gui.engine.roster.is_away(gui.engine.player):
            gui._away_hb = 0
            return
        gui._away_hb = getattr(gui, "_away_hb", 0) + 1
        if gui._away_hb >= HEARTBEAT_FRAMES:
            gui._away_hb = 0
            gui.engine.advance_turn()
    except Exception:
        pass


def banner_text(engine_or_gui):
    """The on-screen AUTOPLAY indicator, or None when the human is at the
    controls. Shown every frame the hero is agent-driven so the player
    always knows autoplay is live and one keypress hands it back — the
    fix for 'autoplay doesn't seem to do anything' (you couldn't tell)."""
    engine = getattr(engine_or_gui, "engine", engine_or_gui)
    try:
        if engine.roster.is_away(engine.player):
            return BANNER
    except Exception:
        pass
    return None
