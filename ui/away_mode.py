"""Absent-player heartbeat (M.3) — while the active hero's human is
away, the game normally freezes (only player actions advance the
world). This ticks the world on a slow cadence so the agent driving
the away hero (via `drive_agents` in the turn pipeline) keeps it, and
the world, alive until the human returns. Any keypress hands back.
"""

HEARTBEAT_FRAMES = 15        # ~0.5s at 30fps between auto-ticks (default)

# M.9b — watchable cadence: how many frames between auto-ticks at each
# speed (None = paused; single-step still works). Slower/faster/pause let
# the watcher follow the story instead of one fixed 0.5s tick.
SPEEDS = [("paused", None), ("slow", 30), ("normal", 15),
          ("fast", 6), ("blitz", 2)]
DEFAULT_SPEED = 2            # "normal" — the old fixed cadence

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
        # the M.9b autoplay-cadence keys never hand back either
        pygame.K_EQUALS, pygame.K_PLUS, pygame.K_KP_PLUS,
        pygame.K_MINUS, pygame.K_KP_MINUS,
        pygame.K_PERIOD, pygame.K_KP_PERIOD,
    })
    _FASTER = frozenset({pygame.K_EQUALS, pygame.K_PLUS, pygame.K_KP_PLUS})
    _SLOWER = frozenset({pygame.K_MINUS, pygame.K_KP_MINUS})
    _STEP = frozenset({pygame.K_PERIOD, pygame.K_KP_PERIOD})
except Exception:                       # headless without pygame
    pygame = None
    _OBSERVE_KEYS = frozenset()
    _FASTER = _SLOWER = _STEP = frozenset()


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


def speed_index(gui) -> int:
    return getattr(gui, "_away_speed", DEFAULT_SPEED)


def speed_label(gui) -> str:
    return SPEEDS[speed_index(gui)][0]


def cycle_speed(gui, step: int) -> str:
    """Slow down / speed up the autoplay cadence; slowing past 'slow'
    reaches 'paused' (M.9b). Returns the new speed's label."""
    gui._away_speed = max(0, min(len(SPEEDS) - 1, speed_index(gui) + step))
    gui._away_hb = 0
    return speed_label(gui)


def single_step(gui) -> None:
    """Advance exactly one world tick — works even while paused, so the
    watcher can step the autoplay hero one action at a time."""
    try:
        gui.engine.advance_turn()
    except Exception:
        pass


def handle_speed_key(gui, event) -> bool:
    """Consume an autoplay-cadence key ([+]/[-]/[.]) while the hero is
    agent-driven. Returns True if it handled the event (so the caller
    neither hands control back nor passes it on)."""
    if pygame is None or getattr(event, "type", None) != pygame.KEYDOWN:
        return False
    k = getattr(event, "key", None)
    if k in _FASTER:
        cycle_speed(gui, 1)
        return True
    if k in _SLOWER:
        cycle_speed(gui, -1)
        return True
    if k in _STEP:
        single_step(gui)
        return True
    return False


def heartbeat(gui) -> None:
    try:
        if not gui.engine.roster.is_away(gui.engine.player):
            gui._away_hb = 0
            return
        interval = SPEEDS[speed_index(gui)][1]
        if interval is None:                # paused — only single-step ticks
            return
        gui._away_hb = getattr(gui, "_away_hb", 0) + 1
        if gui._away_hb >= interval:
            gui._away_hb = 0
            gui.engine.advance_turn()
    except Exception:
        pass


def spectator_lines(engine):
    """A few lines on what the driven hero is up to RIGHT NOW — its aim,
    bearing, standing and band — for the M.9c spectator panel, so watching
    autoplay reads as a story. None when the human is at the controls."""
    try:
        if not engine.roster.is_away(engine.player):
            return None
    except Exception:
        return None
    p = engine.player
    meta = getattr(p, "metadata", {}) or {}
    lines = ["◆ " + getattr(p, "name", "The hero")]
    lines.append(f"Aim: {meta.get('agent_goal') or 'wandering'}")
    try:
        from engine.settings import get_setting
        lines.append(f"Bearing: {get_setting(p, 'disposition')}")
        amb = get_setting(p, "ambition")
        if amb and amb != "none":
            lines.append(f"Ambition: {amb}")
    except Exception:
        pass
    lines.append(f"Lvl {getattr(p, 'level', 1)}  ·  "
                 f"{getattr(p, 'hp', 0)}/{getattr(p, 'max_hp', 0)} HP  ·  "
                 f"{getattr(p, 'gold', 0)}g")
    try:
        party = list(getattr(engine.companion_manager, "party", []) or [])
        names = [engine.npc_manager.npcs[n].name for n in party
                 if n in engine.npc_manager.npcs]
        lines.append("Band: " + (", ".join(names) if names else "alone"))
    except Exception:
        pass
    return lines


def banner_text(engine_or_gui):
    """The on-screen AUTOPLAY indicator (with the current speed + cadence
    controls, M.9b), or None when the human is at the controls."""
    engine = getattr(engine_or_gui, "engine", engine_or_gui)
    try:
        if not engine.roster.is_away(engine.player):
            return None
    except Exception:
        return None
    label = speed_label(engine_or_gui) if hasattr(engine_or_gui, "engine") \
        else "normal"
    return (f"◆ AUTOPLAY [{label}]  ·  [-/+] speed  [.] step  ·  "
            f"move or act to take control")
