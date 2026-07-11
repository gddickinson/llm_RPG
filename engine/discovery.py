"""Fog of war & map discovery (P15.11) — the map is earned.

The overworld starts UNKNOWN. Three states per tile:
  UNSEEN    — never in view; drawn black, hides its actors.
  EXPLORED  — seen once, since left; drawn dim, terrain remembered
              but live NPCs/monsters hidden (you recall the barn,
              not who's in it now).
  VISIBLE   — in the player's FOV this turn; drawn full, actors
              shown.

Each turn `update(engine)` recomputes VISIBLE from the player's
position via the P8.6 shadowcaster (buildings/mountains/forest
block sight) out to effective_visibility(), and folds it into the
persistent EXPLORED set. Reveal also comes from OTHER routes: a
bought/found MAP paints a region explored (`reveal_area`), an NPC
telling you (`reveal_around` a POI), or magic (the Farsight spell
routes here). State is two sets on player.metadata — save-free.

The event log obeys the same eyes: `can_witness(engine, pos)` is
True only when that tile is VISIBLE, so an actor-local line
(a distant spell, a schedule move) is logged only if the player
could see it. World news/rumor ([Realm]/[Board]/[DM]) bypasses
this by design — that's word travelling, not sight.
"""

import logging

logger = logging.getLogger("llm_rpg.discovery")

SIGHT_BONUS = 2          # you see a hair past where you can act


def _explored(engine) -> set:
    raw = engine.player.metadata.setdefault("explored", [])
    if isinstance(raw, list):
        raw = set(tuple(t) for t in raw)
        engine.player.metadata["explored"] = raw
    return raw


def visible_set(engine) -> set:
    """Tiles the player can see RIGHT NOW (cached per turn)."""
    return getattr(engine, "_visible_tiles", set())


def is_visible(engine, x: int, y: int) -> bool:
    return (x, y) in visible_set(engine)


def is_explored(engine, x: int, y: int) -> bool:
    return (x, y) in _explored(engine)


def update(engine) -> None:
    """Recompute the visible set and fold it into explored. Called
    each turn from the pipeline; a no-op inside zones (dungeons
    keep their own fog)."""
    try:
        if engine.active_zone() is not None:
            engine._visible_tiles = set()
            return
    except Exception:
        pass
    from world.fov import _overworld_opaque, compute_fov
    wmap = engine.world.map
    px, py = engine.player.position
    try:
        radius = engine.effective_visibility() + SIGHT_BONUS
    except Exception:
        radius = 8
    vis = compute_fov(px, py, radius, _overworld_opaque(wmap),
                      wmap.width, wmap.height)
    engine._visible_tiles = vis
    _explored(engine).update(vis)


def actor_hidden(engine, npc) -> bool:
    """An NPC/monster on an unseen tile is not shown or targetable
    (P15.11) — overworld only; zone actors use zone fog."""
    try:
        if engine.active_zone() is not None:
            return False
        if npc.metadata.get("zone") is not None:
            return False
    except Exception:
        return False
    return not is_visible(engine, *npc.position)


def can_witness(engine, pos) -> bool:
    """The event-log gate: True only if the player can SEE the
    tile (fresh line-of-sight, so it's correct any time — not just
    after a turn tick). Actor-local log lines route through here."""
    try:
        if engine.active_zone() is not None:
            return True     # zones are small; you're in the room
    except Exception:
        return True
    try:
        from world.fov import overworld_los
        px, py = engine.player.position
        return overworld_los(engine, (px, py),
                             (int(pos[0]), int(pos[1])))
    except Exception:
        return True


# ---- reveal routes ------------------------------------------------

def reveal_around(engine, x: int, y: int, radius: int = 6) -> int:
    """Mark a disc explored (an NPC's directions, a signpost).
    Returns tiles newly revealed."""
    wmap = engine.world.map
    ex = _explored(engine)
    n0 = len(ex)
    for yy in range(y - radius, y + radius + 1):
        for xx in range(x - radius, x + radius + 1):
            if 0 <= xx < wmap.width and 0 <= yy < wmap.height and \
                    (xx - x) ** 2 + (yy - y) ** 2 <= radius * radius:
                ex.add((xx, yy))
    return len(ex) - n0


def reveal_area(engine, cx: int, cy: int, w: int, h: int) -> int:
    """A bought/found map paints a rectangle explored."""
    wmap = engine.world.map
    ex = _explored(engine)
    n0 = len(ex)
    for yy in range(cy - h // 2, cy + h // 2 + 1):
        for xx in range(cx - w // 2, cx + w // 2 + 1):
            if 0 <= xx < wmap.width and 0 <= yy < wmap.height:
                ex.add((xx, yy))
    return len(ex) - n0


def use_map_item(engine, item) -> str:
    """A 'map' item (use_effect.reveal) paints the land it charts.
    reveal='settlements' charts every town; reveal='all' the whole
    map; or a location-name substring charts that place."""
    target = (getattr(item, "use_effect", None) or {}).get("reveal")
    if not target:
        return ""
    wmap = engine.world.map
    if target == "all":
        n = reveal_area(engine, wmap.width // 2, wmap.height // 2,
                        wmap.width, wmap.height)
        return f"The map fills in the whole realm. ({n} tiles)"
    if target == "settlements":
        n = 0
        for loc in engine.world.locations:
            if any(k in loc.name for k in ("Village", "Hamlet",
                                           "Camp")):
                n += reveal_around(
                    engine, loc.x + loc.width // 2,
                    loc.y + loc.height // 2, radius=8)
        return f"Every settlement is charted now. ({n} tiles)"
    loc = next((l for l in engine.world.locations
                if target.lower() in l.name.lower()), None)
    if loc is not None:
        n = reveal_around(engine, loc.x + loc.width // 2,
                          loc.y + loc.height // 2, radius=8)
        return f"The way to {loc.name} is clear on the map. ({n})"
    return "The map shows nowhere you don't already know."
