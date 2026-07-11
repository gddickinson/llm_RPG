"""Absent-player heartbeat (M.3) — while the active hero's human is
away, the game normally freezes (only player actions advance the
world). This ticks the world on a slow cadence so the agent driving
the away hero (via `drive_agents` in the turn pipeline) keeps it, and
the world, alive until the human returns. Any keypress hands back.
"""

HEARTBEAT_FRAMES = 15        # ~0.5s at 30fps between auto-ticks


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
