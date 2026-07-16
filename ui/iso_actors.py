"""ISO.8 — actor-motion helpers for the isometric render path.

Split from `iso_render` (500-line line) so the character-motion logic the world
and interior paths SHARE lives in one small place: which characters the iso view
draws (`visible_chars`), and the smooth tile-to-tile SLIDE (`tween_world_pos`)
that makes an iso step read as continuous motion instead of a teleport. Both
`iso_render.render_iso` and `iso_zone.render_zone_iso` import from here.
"""

DT = 1.0 / 30.0                  # anim advance per frame (matches top-down)


def tween_world_pos(char, cx, cy):
    """The FRACTIONAL world position a character is sliding through — it eases
    from its previous tile toward its current one over the body_renderer TWEEN,
    so an iso step reads as continuous motion, not a teleport. Falls back to the
    logical tile once the tween has run out (or when there's no anim)."""
    anim = (getattr(char, "metadata", {}) or {}).get("_anim")
    if not anim:
        return float(cx), float(cy)
    from ui.body_renderer import TWEEN_DUR
    t = anim.get("tween_t", 0.0)
    fr = anim.get("tween_from")
    if t > 0 and fr and TWEEN_DUR > 0:
        k = t / TWEEN_DUR                          # 1 at the step, 0 at arrival
        return cx + fr[0] * k, cy + fr[1] * k
    return float(cx), float(cy)


def visible_chars(engine):
    """Hero + active NPCs the top-down view would show (not wall-hidden)."""
    out = [engine.player]
    try:
        from engine.presence import hidden_by_walls
    except Exception:
        hidden_by_walls = None
    for npc in engine.npc_manager.npcs.values():
        if not (hasattr(npc, "is_active") and npc.is_active()):
            continue
        if hidden_by_walls is not None and hidden_by_walls(engine, npc):
            continue
        out.append(npc)
    return out
