"""Frame-by-frame projectile animation so a ranged shot is SEEN in flight
(George: arrows should be seen fired), rather than resolving instantly in the
turn pipeline. The GUI enables it and ticks it once per rendered frame; the
arrow flies ~0.3s and resolves the hit on arrival, with a grey 'miss' popup
when it goes wide. Headless / turn-based play keeps the instant resolution.
"""

import logging

logger = logging.getLogger("llm_rpg.projectile_anim")

ANIM_DT = 0.14          # turns advanced per frame → a visible ~0.3s flight


def enable(engine) -> None:
    """Defer projectile resolution to the frame animation (see turn_pipeline)."""
    try:
        engine.animate_projectiles = True
    except Exception:
        pass


def frame_tick(engine) -> None:
    """Advance in-flight arrows/bolts a little; resolve + effect on arrival."""
    pm = getattr(engine, "projectile_manager", None)
    if not pm or not pm.active:
        return
    try:
        for r in pm.tick(dt=ANIM_DT):
            if r.message:
                engine.memory_manager.add_event(r.message)
            if not r.hit:
                ce = getattr(engine, "combat_effects", None)
                if ce:
                    ce.on_miss_at(r.x, r.y)
    except Exception as e:
        logger.debug(f"projectile animation error: {e}")
