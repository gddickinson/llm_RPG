"""P33.6c animation triggers — engine-side, pygame-free.

Game code calls these to make a character PLAY an animation; they only set the
`metadata` keys the UI's `body_renderer` reads (`_emote` one-shots, `_stance`
held loops, `_face` a heading). No UI import, so the engine stays headless.
"""


def emote(char, name):
    """Request a one-shot clip (stoop / kneel / reach / point / bow / wave …)."""
    try:
        char.metadata["_emote"] = name
    except Exception:
        pass


def stance(char, name):
    """Hold a looping stance (swim / climb / sit / guard / sneak), or None."""
    try:
        if name:
            char.metadata["_stance"] = name
        else:
            char.metadata.pop("_stance", None)
    except Exception:
        pass


def express(char, name):
    """Set the held facial expression (happy/angry/sad/scared/hurt/…) (P34.2)."""
    try:
        char.metadata["_expr"] = name
    except Exception:
        pass


def bubble(char, kind):
    """Pop a symbol bubble above the head (alert/question/sleep/love/angry/note)."""
    try:
        char.metadata["_bubble"] = kind
    except Exception:
        pass


def face(char, target_pos):
    """Turn a character to face a tile it acts on."""
    try:
        px, py = char.position
        dx, dy = target_pos[0] - px, target_pos[1] - py
        if dx or dy:
            char.metadata["_face"] = ((1 if dx > 0 else -1, 0) if abs(dx) >= abs(dy)
                                      else (0, 1 if dy > 0 else -1))
    except Exception:
        pass


# P33.6d — a two-character interaction assigns each side its half + faces them
_INTERACTIONS = {
    "handshake": ("handshake", "handshake"),
    "hug": ("hug", "hug"),
    "kiss": ("kiss", "kiss"),
    "wrestle": ("wrestle", "wrestle"),
    "throw": ("throw", "tumble"),          # a throws, b flies
    "knockdown": ("attack", "knockdown"),  # a strikes, b falls & rises
    "guard": ("guard", None),              # a shields b (b unposed)
}


def interact(a, b, kind):
    """Play a coordinated two-character interaction (handshake / hug / kiss /
    wrestle / throw / knockdown / guard): each turns to face the other and plays
    its half. Reads as one motion because the two stand adjacent (P33.6d)."""
    ca, cb = _INTERACTIONS.get(kind, (kind, kind))
    if b is not None:
        face(a, b.position)
        face(b, a.position)
        if cb:
            emote(b, cb)
    if ca:
        emote(a, ca)


def look(char, target_pos):
    """Make a character's head/eyes glance toward a tile (None to clear)."""
    try:
        if target_pos is None:
            char.metadata.pop("_look", None)
        else:
            char.metadata["_look"] = tuple(target_pos)
    except Exception:
        pass


def update_look(engine, radius=8):
    """Per-turn: each visible character GLANCES at the nearest other actor within
    `radius` tiles (the player at least), so the cast watches each other and you
    (P34.3). Cheap O(n²) over the small open-world cast."""
    try:
        cast = [n for n in engine.npc_manager.npcs.values() if n.is_active()]
        cast.append(engine.player)
        r2 = radius * radius
        for c in cast:
            if (c.metadata or {}).get("_stance") == "sit":
                continue
            best, bd = None, r2 + 1
            cx, cy = c.position
            for o in cast:
                if o is c:
                    continue
                d = (o.position[0] - cx) ** 2 + (o.position[1] - cy) ** 2
                if d < bd:
                    bd, best = d, o
            c.metadata["_look"] = best.position if best else None
    except Exception:
        pass


# P34.4 ambient idle life — a pool of small fidgets an idle body plays now and then
_FIDGETS = ("stretch", "yawn", "shrug", "ponder", "wave")


def _idle_fidget(char, rng):
    """A fidget flavoured by the character's needs / role, else the generic pool."""
    try:
        from characters.needs import get_fatigue
        if get_fatigue(char) >= 60 and rng.random() < 0.6:
            return "yawn" if rng.random() < 0.5 else "stretch"
    except Exception:
        pass
    role = getattr(getattr(char, "character_class", None), "value", "")
    if role == "merchant" and rng.random() < 0.6:
        return "beckon" if rng.random() < 0.5 else "wave"
    if role in ("wizard", "sorcerer", "warlock", "cleric", "druid") \
            and rng.random() < 0.5:
        return "ponder"
    if role in ("guard", "warrior", "paladin") and rng.random() < 0.4:
        return "salute"
    return rng.choice(_FIDGETS)


def _nearest(pool, c, radius):
    cx, cy = c.position
    best, bd = None, radius * radius + 1
    for o in pool:
        if o is c:
            continue
        d = (o.position[0] - cx) ** 2 + (o.position[1] - cy) ** 2
        if d < bd:
            bd, best = d, o
    return best


def update_idle_life(engine, rng=None, chance=0.025):
    """Per-turn ambient life (P34.4): an idle, non-hostile character occasionally
    plays a small fidget (weighted by role/needs); a townsfolk near a hostile
    startles instead — an alert bubble + turns to face the threat. Cheap and purely
    cosmetic (sets only the UI `metadata` the renderer reads). `rng` is injectable
    for tests."""
    import random as _r
    from engine.agent_sense import _is_hostile
    rng = rng or _r
    try:
        cast = [n for n in engine.npc_manager.npcs.values() if n.is_active()]
        cast.append(engine.player)
        hostiles = [h for h in cast if _is_hostile(h)]
        for c in cast:
            meta = getattr(c, "metadata", None)
            if not isinstance(meta, dict):
                continue
            if meta.get("_emote") or meta.get("_stance"):
                continue                        # already busy
            if (meta.get("_anim") or {}).get("moving"):
                continue                        # mid-stride — don't cut a step
            if _is_hostile(c):
                continue                        # monsters don't yawn
            near = _nearest(hostiles, c, 5)
            if near is not None:
                if rng.random() < chance * 2:
                    face(c, near.position)
                    bubble(c, "alert")
                continue
            if rng.random() < chance:
                fid = _idle_fidget(c, rng)
                if fid:
                    emote(c, fid)
    except Exception:
        pass


def update_swim(engine):
    """Per-turn: the hero shows a SWIM stance while standing on deep water, and
    drops it again on dry land (P33.6c)."""
    try:
        from world.world_map import TerrainType
        p = engine.player
        terrain = engine.world.map.get_terrain_at(*p.position)
        cur = (p.metadata or {}).get("_stance")
        if terrain == TerrainType.WATER:
            p.metadata["_stance"] = "swim"
        elif cur == "swim":
            p.metadata.pop("_stance", None)
    except Exception:
        pass
