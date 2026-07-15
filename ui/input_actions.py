"""Play-mode action helpers split out of `input_handler` to hold that
file under the 500-line rule: look-around, party toggle, open-shop.

Each takes the `InputHandler` (or its engine) so they can reach the engine
and gui without duplicating the wiring.
"""


def look_around(engine) -> None:
    try:
        x, y = engine.player.position
        visible = engine.world.map.get_visible_description(x, y)
        for line in visible.split("\n"):
            if line.strip():
                engine.memory_manager.add_event(line)
    except Exception:
        pass


def toggle_party(handler) -> None:
    """P key — dismiss an adjacent party member, or try to recruit."""
    engine = handler.engine
    try:
        npc = handler._find_adjacent_npc()
        if npc is None:
            engine.memory_manager.add_event("No one nearby to recruit.")
            return
        if npc.id in engine.companion_manager.party:
            engine.dismiss_companion(npc.id)
            return
        msg = engine.recruit(npc.id)
        # Success is logged by the manager; log refusals too
        if "joins your party" not in msg:
            engine.memory_manager.add_event(msg)
    except Exception:
        pass


def _adjacent_foe(engine) -> bool:
    try:
        from engine.tactics import adjacent_hostiles
        return bool(adjacent_hostiles(engine, engine.player.position))
    except Exception:
        return False


def step(handler, dx: int, dy: int, shift: bool) -> bool:
    """P34.9 one player stride (macOS-safe rebind). Holding SHIFT means MOVE
    DELIBERATELY, resolved by context: next to a foe it's the careful DISENGAGE
    (no opportunity strike); in the clear it's a RUN — the running animation plus a
    sprint that covers a bonus tile when the way stays open (`move_player` no-ops if
    that second stride is blocked, so a wall just stops the sprint). P34.12: while
    CRAWLING you go prone — no sprint, no careful, just a slow stride."""
    engine = handler.engine
    p = engine.player
    if (p.metadata or {}).get("_move_mode") == "crawl":
        p.metadata.pop("_running", None)
        engine.move_player(dx, dy)
        return True
    near_foe = _adjacent_foe(engine)
    careful = bool(shift and near_foe)
    # P34.16 a sprint costs STAMINA; winded → the SHIFT just walks (no sprint)
    from engine import stamina
    want_run = bool(shift and not near_foe)
    run = want_run and stamina.can_run(p)
    try:
        if run:
            was_winded = stamina.is_winded(p)
            p.metadata["_running"] = True
            stamina.spend(p, engine)
            if stamina.is_winded(p) and not was_winded:
                from engine import anim
                anim.emote(p, "winded")
                engine.memory_manager.add_event(
                    "[!] You're out of breath — ease off the sprint.")
        else:
            p.metadata.pop("_running", None)
    except Exception:
        pass
    moved = engine.move_player(dx, dy, careful=careful)
    if run and moved and (dx or dy):
        engine.move_player(dx, dy, careful=careful)      # bonus running stride
        try:
            stamina.spend(p, engine)
        except Exception:
            pass
    return True


# P34.12 held-to-move (key repeat) + movement-pace modes ------------------
REPEAT_DELAY = 200        # ms a key must be held before it auto-repeats
_PACE_MS = {"crawl": 250, "jog": 120, "run": 115, "walk": 160}
_MOVE_MODES = (None, "jog", "crawl")


def _held_dir(keys):
    """Sum the currently-held movement keys into a single (dx, dy) step."""
    import pygame
    dx = dy = 0
    if keys[pygame.K_w] or keys[pygame.K_UP]:
        dy -= 1
    if keys[pygame.K_s] or keys[pygame.K_DOWN]:
        dy += 1
    if keys[pygame.K_a] or keys[pygame.K_LEFT]:
        dx -= 1
    if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
        dx += 1
    for k, (kx, ky) in ((pygame.K_KP8, (0, -1)), (pygame.K_KP2, (0, 1)),
                        (pygame.K_KP4, (-1, 0)), (pygame.K_KP6, (1, 0)),
                        (pygame.K_KP7, (-1, -1)), (pygame.K_KP9, (1, -1)),
                        (pygame.K_KP1, (-1, 1)), (pygame.K_KP3, (1, 1))):
        if keys[k]:
            dx += kx
            dy += ky
    return max(-1, min(1, dx)), max(-1, min(1, dy))


def auto_walk(handler) -> bool:
    """Held movement keys keep the hero stepping (George): a tap is one step, but
    HOLDING a direction walks / runs continuously. The first step comes from the
    KEYDOWN; after `REPEAT_DELAY` this repeats at the pace of the current mode.
    Returns True if it issued an auto-step this frame. Call once per frame in play
    mode."""
    import pygame
    keys = pygame.key.get_pressed()
    dx, dy = _held_dir(keys)
    now = pygame.time.get_ticks()
    if dx == 0 and dy == 0:
        handler._auto_dir = None
        return False
    shift = bool(keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT])
    if getattr(handler, "_auto_dir", None) != (dx, dy):
        handler._auto_dir = (dx, dy)                 # the KEYDOWN already stepped;
        handler._auto_next = now + REPEAT_DELAY      # wait before repeating
        return False
    if now < getattr(handler, "_auto_next", 0):
        return False
    step(handler, dx, dy, shift)
    mode = (handler.engine.player.metadata or {}).get("_move_mode")
    pace = ("crawl" if mode == "crawl" else "run" if shift
            else "jog" if mode == "jog" else "walk")
    handler._auto_next = now + _PACE_MS[pace]
    return True


# P34.13 the emote/dance key — a random comedy move each press
_EMOTES = ("dance", "jig", "kick", "moonwalk", "robot", "flex", "taunt",
           "wiggle", "disco", "airguitar", "cheer", "wave", "bow", "laugh",
           "twirl", "clap")


def perform_emote(handler) -> bool:
    """`;` performs a random dance / jig / taunt — the hero shows off (P34.13)."""
    import random
    from engine import anim
    move = random.choice(_EMOTES)
    anim.emote(handler.engine.player, move)
    try:
        handler.engine.memory_manager.add_event(f"[Emote] you {move}.")
    except Exception:
        pass
    return True


def cycle_move_mode(handler) -> bool:
    """`.` cycles the walking PACE: walk → jog → crawl → walk (P34.12)."""
    p = handler.engine.player
    cur = (p.metadata or {}).get("_move_mode")
    nxt = _MOVE_MODES[(_MOVE_MODES.index(cur) + 1) % len(_MOVE_MODES)] \
        if cur in _MOVE_MODES else "jog"
    if nxt is None:
        p.metadata.pop("_move_mode", None)
    else:
        p.metadata["_move_mode"] = nxt
    try:
        handler.engine.memory_manager.add_event(f"[Move] {nxt or 'walk'} pace.")
    except Exception:
        pass
    return True


def _facing(p):
    a = (p.metadata or {}).get("_anim") or {}
    fx, fy = a.get("facing", (0, 1))
    return int(fx), int(fy)


def _momentum_move(handler, clip, tiles=2) -> bool:
    """P34.20 a running special move — play `clip` and surge `tiles` forward while
    the way is open, spending stamina per tile (blocked = it stops there)."""
    from engine import anim, stamina
    engine = handler.engine
    p = engine.player
    anim.emote(p, clip)
    dx, dy = _facing(p)
    moved = 0
    if dx or dy:
        for _ in range(tiles):
            if engine.move_player(dx, dy):
                moved += 1
                try:
                    stamina.spend(p, engine)
                except Exception:
                    pass
            else:
                break
    if not moved:
        engine.move_player(0, 0)
    return True


def jump(handler) -> bool:
    """P34.9 `` ` ``: the hero LEAPS — a forward hop, else in place. P34.20: with
    RUNNING momentum it becomes a DIVE-ROLL (a tumbling surge forward)."""
    engine = handler.engine
    p = engine.player
    if (p.metadata or {}).get("_running"):               # momentum → dive-roll
        return _momentum_move(handler, "roll", tiles=2)
    from engine import anim
    anim.emote(p, "jump")
    try:
        from engine import stamina
        stamina.spend_action(p, engine=engine)           # a hop is exertion too
    except Exception:
        pass
    dx, dy = _facing(p)
    if (dx or dy) and engine.move_player(dx, dy):
        return True                                      # leapt forward a tile
    engine.move_player(0, 0)                              # in-place hop, still a beat
    return True


def slide(handler) -> bool:
    """P34.20 `'`: a running SLIDE — only with momentum from a sprint (else a nudge
    to get a running start)."""
    p = handler.engine.player
    if not (p.metadata or {}).get("_running"):
        try:
            handler.engine.memory_manager.add_event(
                "[!] You need a running start to slide.")
        except Exception:
            pass
        return True
    return _momentum_move(handler, "slide", tiles=2)


def open_shop(handler) -> None:
    engine, gui = handler.engine, handler.gui
    try:
        from engine.shop import merchants_near
        merchants = merchants_near(engine, engine.player, radius=2.0)
        if not merchants:
            engine.memory_manager.add_event("There's no merchant nearby.")
            return
        refusal = engine.shop_manager.trade_refusal(
            engine.player, merchants[0])   # P12.11
        if refusal:
            engine.memory_manager.add_event(refusal)
            return
        gui.show_shop(merchants[0])
    except Exception:
        pass


def one_key_overlay(gui, k) -> bool:
    """Single-key overlays: collection / diaries / travel / topics / settings."""
    import pygame
    overlays = {pygame.K_o: gui.show_collection_log,
                pygame.K_j: gui.show_diaries,
                pygame.K_u: gui.show_travel,
                pygame.K_y: gui.show_topics,
                pygame.K_COMMA: gui.show_settings}
    fn = overlays.get(k)
    if fn is None:
        return False
    fn()
    return True


def number_key(engine, k) -> bool:
    """Play-mode number keys 1-5: answer a guard's confrontation (P12.9) if one
    is active, else NON-BLOCKING quick-cast the spell in that quick-slot (P22.6)."""
    import pygame
    if not (pygame.K_1 <= k <= pygame.K_5):
        return False
    n = k - pygame.K_1
    if getattr(engine.law, "active", None):
        engine.law.resolve(n + 1)
        return True
    from engine.quick_spells import quick_cast
    quick_cast(engine, n)
    return True


def skill_verb(engine, k) -> bool:
    """PF2e combat verbs (P12.8): SHIFT + T/I/B/H → trip/demoralize/feint/medicine."""
    import pygame
    verbs = (pygame.K_t, pygame.K_i, pygame.K_b, pygame.K_h)
    if k not in verbs:
        return False
    from engine import skill_actions as sa
    {pygame.K_t: sa.trip, pygame.K_i: sa.demoralize,
     pygame.K_b: sa.feint, pygame.K_h: sa.battle_medicine}[k](engine)
    return True


def menu_mode_key(gui, engine, event) -> bool:
    """The numbered pop-up menus — travel (P11) / stable (P28.2d) / waystone
    (P37.1): 1-9 picks an entry, Esc (or the opening key) leaves. Returns True
    if handled, None if `gui.mode` isn't one of these menus."""
    import pygame
    mode = gui.mode
    if mode not in ("travel", "stable", "waystone"):
        return None
    if event.type != pygame.KEYDOWN:
        return True
    exits = {"travel": (pygame.K_ESCAPE, pygame.K_u),
             "stable": (pygame.K_ESCAPE, pygame.K_e, pygame.K_g),
             "waystone": (pygame.K_ESCAPE, pygame.K_e, pygame.K_g)}
    if event.key in exits[mode]:
        gui.mode = "play"
        gui.overlay = None
        return True
    if pygame.K_1 <= event.key <= pygame.K_9:
        idx = event.key - pygame.K_1
        try:
            if mode == "travel":
                engine.travel_system.teleport(idx)
            elif mode == "stable":
                engine.mount_stable_buy(idx)
            else:
                engine.memory_manager.add_event(
                    engine.teleport_network.teleport_index(idx))
        except Exception:
            pass
        gui.mode = "play"
        gui.overlay = None
        return True
    return True
