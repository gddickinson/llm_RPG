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
    dur = anim.get("tween_dur", TWEEN_DUR) or TWEEN_DUR
    if t > 0 and fr and dur > 0:
        k = t / dur                                # 1 at the step, 0 at arrival
        return cx + fr[0] * k, cy + fr[1] * k
    return float(cx), float(cy)


def beast_sprite(char, tile_size):
    """#9 — a baked Quaternius GLB model for a beast-class creature (the models
    are baked at the iso camera, so they drop straight into the iso view), or
    None so the caller uses the humanoid iso figure. Gated to non-humanoid body
    plans so an NPC named 'Wolfgang' never becomes a wolf."""
    from ui import creature_pose
    if creature_pose.body_plan(char) == "humanoid":
        return None
    from ui import creature_anim, creature_glb, iso_chars
    face_east = iso_chars.move_delta(char)[0] > 0
    size = int(tile_size * creature_glb.scale_for(char))
    return (creature_anim.animated_sprite(char, size, face_east=face_east)   # #9b
            or creature_glb.sprite_for_char(char, size, face_east=face_east))


def draw_actor(target, char, sx, sy, tile_size):
    """Draw one iso actor at screen (sx, sy): a contact shadow, then either a
    baked GLB creature model (beasts — #9) or the humanoid iso figure. Shared by
    the world (`iso_render`) and interior (`iso_zone`) paths."""
    import pygame
    from ui import iso_chars
    th = max(6, tile_size // 3)
    sh = pygame.Surface((tile_size, th), pygame.SRCALPHA)
    pygame.draw.ellipse(sh, (0, 0, 0, 95), (0, 0, tile_size, th))
    target.blit(sh, (sx - tile_size // 2, sy - th // 2))       # contact shadow
    spr = beast_sprite(char, tile_size)
    if spr is not None:                          # a grounded quadruped/creature
        w, h = spr.get_size()
        target.blit(spr, (sx - w // 2, sy - int(h * 0.62)))
    else:
        spr = iso_chars.char_sprite(char, int(tile_size * 1.5))
        w, h = spr.get_size()
        target.blit(spr, (sx - w // 2, sy - int(h * 0.72)))


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
