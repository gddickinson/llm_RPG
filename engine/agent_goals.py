"""Away-agent exploration goals & disposition (split from
`agent_controller` to hold the 500-line line). Where a hero of a given
calling is drawn to roam, and how the player asked it to behave. Functions
take the controller as `ctrl` so they can read/write its `visited` /
`goal_name` / `home` / `rng` state.
"""

# class -> the kinds of named place a hero of that calling is drawn to
CLASS_DRAW = {
    "warrior": ("lair", "warren", "den", "keep", "cave", "ruin"),
    "barbarian": ("lair", "den", "cave", "warren"),
    "paladin": ("keep", "temple", "shrine", "lair"),
    "wizard": ("tower", "stones", "shrine", "barrow", "temple"),
    "sorcerer": ("tower", "stones", "barrow"),
    "warlock": ("barrow", "stones", "hollow", "tower"),
    "rogue": ("cave", "market", "ruin", "barrow", "hollow"),
    "ranger": ("hollow", "camp", "cave", "forest", "ruin"),
    "druid": ("hollow", "shrine", "stones", "forest"),
    "cleric": ("temple", "shrine", "chapel"),
    "monk": ("temple", "shrine", "stones"),
    "bard": ("tavern", "market", "inn", "village"),
}

ROAM = 10                 # how far an idle away hero strikes out

# M.9d — a high-level AMBITION the player sets for the absence draws the
# hero to the kinds of place that serve it, OVERRIDING the class calling
AMBITION_DRAW = {
    "wealth": ("market", "town", "village", "hamlet", "shop", "camp"),
    "delve": ("cave", "ruin", "keep", "lair", "hollow", "barrow",
              "warren", "den", "crypt", "dungeon"),
    "mastery": ("tower", "stones", "barrow", "shrine", "temple", "college"),
    "fellowship": ("tavern", "inn", "guild", "hall", "village", "hamlet"),
}


def ambition(char) -> str:
    try:
        from engine.settings import get_setting
        return str(get_setting(char, "ambition") or "none").lower()
    except Exception:
        return "none"


def battle_ready(char) -> bool:
    """Hale enough to go LOOKING for a fight — healthy and carrying a way to
    recover mid-battle (a heal potion or a heal spell), and not the timid
    sort. A hurt, unprovisioned, or cautious hero sticks to safer roaming."""
    if disposition(char) == "cautious":
        return False
    if char.hp < char.max_hp * 0.75:
        return False
    from engine.agent_sense import _healing_item, _knows_heal
    return _healing_item(char) is not None or _knows_heal(char)


def adventure_lair(engine, char, avoid=()):
    """The nearest UNCLEARED lair the hero (and band) can plausibly CLEAR and
    hasn't given up on — (pos, name), or None. Weighs the den's TOTAL and
    TOUGHEST defenders against the party's capacity, so a fresh hero takes a
    small goblin warren but never charges a troll den or a warband to its
    death. Reads `engine.lairs`; state-free."""
    ls = getattr(engine, "lairs", None)
    if ls is None:
        return None
    px, py = char.position
    cap = getattr(char, "level", 1) + max(1, char.hp // 8)
    try:
        cap += 2 * len(getattr(engine.companion_manager, "party", []))
    except Exception:
        pass
    hero = getattr(char, "level", 1)
    best, bd = None, None
    for lair in getattr(ls, "lairs", []):
        if lair.get("cleared") or lair.get("name", "") in avoid:
            continue
        threat, toughest = 0, 0
        for oid in lair.get("occupants", []):
            occ = engine.npc_manager.get_npc(oid)
            if occ is not None and occ.is_active():
                lvl = max(1, getattr(occ, "level", 1))
                threat += lvl
                toughest = max(toughest, lvl)
        if threat > cap or toughest > hero + 1:
            continue
        pos = tuple(lair.get("pos", (0, 0)))
        d = (pos[0] - px) ** 2 + (pos[1] - py) ** 2
        if bd is None or d < bd:
            best, bd = (pos, lair.get("name", "")), d
    return best


def named_goal(ctrl, engine, char):
    """The nearest UNVISITED named place the hero is drawn to — its AMBITION
    (M.9d) if the player set one, else its class calling. Records the choice
    on `ctrl.goal_name`."""
    # SEEK ADVENTURE (George) — a battle-ready hero strikes out for a DEN it
    # can clear (XP + a hoard). It rides this rule's SAFE stall-and-abandon
    # roaming (pathing never dead-ends — `safe_step` always routes or waits),
    # and the manageable-lair gate keeps it from a suicidal delve. If it can't
    # reach the den (stalls out), rule 7 marks the name visited and it moves
    # on to the next one — so seeking a fight can never freeze it.
    # LIVE A RICH LIFE (George) — before roaming, a social hero forms a party
    # and takes on a quest: head to the nearest recruitable adventurer (gather
    # a band), then to the nearest quest-giver (go adventuring). These use the
    # SAME safe stall/TTL roaming as any goal, so a far target never freezes it.
    if getattr(ctrl, "social", False):
        rec = nearest_recruitable(ctrl, engine, char)
        if rec is not None:
            ctrl.goal_name = f"recruit {rec[0]}"
            return reachable_tile(engine, char, rec[1])
        try:
            has_quest = bool(engine.quest_manager.active())
        except Exception:
            has_quest = True
        if not has_quest:
            qg = nearest_quest_giver(engine, char)
            if qg is not None:
                ctrl.goal_name = f"{qg[0]} — a quest"
                return reachable_tile(engine, char, qg[1])
    try:
        if battle_ready(char):
            al = adventure_lair(engine, char, ctrl.visited)
            if al is not None:
                ctrl.goal_name = al[1]
                return al[0]
    except Exception:
        pass
    cls = getattr(getattr(char, "character_class", None), "value", "")
    draw = AMBITION_DRAW.get(ambition(char)) or CLASS_DRAW.get(cls, ())
    # SEEK COMPANIONS (George) — a partyless hero with room to grow a band is
    # DRAWN to a guild hall, where adventurers gather to be recruited. Folded
    # into the class draw so it rides rule 7's safe stall-and-abandon roaming
    # (a dedicated cross-map march kept dead-ending in rough terrain).
    try:
        if ctrl._room_in_party(engine) \
                and not engine.companion_manager.party:
            draw = tuple(draw) + ("guild", "hall", "adventurers",
                                  "mercenaries")
    except Exception:
        pass
    px, py = char.position
    pref, other = [], []
    for loc in getattr(engine.world, "locations", []):
        if loc.name in ctrl.visited:
            continue
        cx, cy = loc.center()
        d = (cx - px) ** 2 + (cy - py) ** 2
        low = loc.name.lower()
        (pref if any(k in low for k in draw) else other).append((d, loc))
    pool = pref or other
    if not pool:
        return None
    pool.sort(key=lambda t: t[0])
    loc = pool[0][1]
    ctrl.goal_name = loc.name
    return reachable_tile(engine, char, loc.center())


def disposition(char) -> str:
    """How the player asked the hero to behave in their absence."""
    try:
        from engine.settings import get_setting
        d = get_setting(char, "disposition")
        if d:
            return str(d).lower()
    except Exception:
        pass
    return (getattr(char, "metadata", {}) or {}).get("disposition", "balanced")


def stalemate_flee(ctrl, engine, char, target):
    """Break off a fight we can't FINISH. Grinding a foe whose HP won't drop
    — a regenerator we can't out-damage — is an endless in-place freeze
    (George: a barbarian traded blows with a troll for 700 turns). After a
    long fruitless streak on one target, returns a flee step, else None."""
    from engine.agent_nav import flee_step
    tid = getattr(target, "id", None)
    hp = getattr(target, "hp", 0)
    if tid == getattr(ctrl, "_atk_id", None) and hp >= getattr(ctrl, "_atk_hp", hp):
        ctrl._atk_n = getattr(ctrl, "_atk_n", 0) + 1   # no progress this streak
    else:
        ctrl._atk_n = 0
    ctrl._atk_id, ctrl._atk_hp = tid, hp
    if ctrl._atk_n > 30:
        step = flee_step(engine, char, target.position, ctrl.recent)
        if step is not None:
            ctrl._atk_n = 0
            ctrl.target_id = None    # drop the fixation so we don't re-lock it
            return step
    return None


def nearest_quest_giver(engine, char):
    """The nearest NPC with a quest ON OFFER — a social hero with no quest of
    its own heads there to TAKE one (so it actually goes adventuring)."""
    qm = getattr(engine, "quest_manager", None)
    if qm is None:
        return None
    px, py = char.position
    best, bd = None, 1e18
    for npc in engine.npc_manager.npcs.values():
        if not npc.is_active():
            continue
        try:
            if not qm.offered_by(npc.id):
                continue
        except Exception:
            continue
        d = (npc.position[0] - px) ** 2 + (npc.position[1] - py) ** 2
        if d < bd:
            best, bd = npc, d
    return (best.name, tuple(best.position)) if best else None


def nearest_recruitable(ctrl, engine, char):
    """The nearest adventurer a PARTYLESS hero (with room) could recruit — so
    it goes to a guild hall and gathers a band instead of adventuring alone."""
    try:
        if not ctrl._room_in_party(engine) or engine.companion_manager.party:
            return None
    except Exception:
        return None
    cm = engine.companion_manager
    px, py = char.position
    best, bd = None, 1e18
    for npc in engine.npc_manager.npcs.values():
        if not npc.is_active() or not npc.metadata.get("adventurer"):
            continue
        try:
            if cm.can_recruit(npc) != "":
                continue
        except Exception:
            continue
        d = (npc.position[0] - px) ** 2 + (npc.position[1] - py) ** 2
        if d < bd:
            best, bd = npc, d
    return (best.name, tuple(best.position)) if best else None


def reachable_tile(engine, char, pos):
    """A WALKABLE tile at/near a location's centre. A hero can't stand ON a
    building, so an exploration goal set to a building CENTRE never 'arrives' —
    the hero circles the wall forever (George: "wanders in a circle"). Snap the
    goal to the nearest open tile so it actually reaches the place and moves on."""
    from engine import agent_nav as nav
    cx, cy = int(pos[0]), int(pos[1])
    if nav.walkable(engine, char, (cx, cy)):
        return (cx, cy)
    for r in range(1, 7):
        best = None
        for dx in range(-r, r + 1):
            for dy in range(-r, r + 1):
                if max(abs(dx), abs(dy)) != r:
                    continue
                t = (cx + dx, cy + dy)
                if nav.walkable(engine, char, t):
                    return t
    return (cx, cy)


def pack_outmatches(char, pack) -> bool:
    """Would this pack likely overwhelm the hero? Weigh the hero's level and
    current HP against the pack's summed strength — generous to the hero
    (gear + a healthy body beat a rabble), so it flees only a clearly
    superior warband, not every three goblins."""
    hero = getattr(char, "level", 1) + max(1, char.hp // 8)
    threat = sum(max(1, getattr(f, "level", 1)) for f in pack)
    return threat > hero * 1.3


def pick_goal(ctrl, engine, char):
    """An away hero potters back toward home (M.3); otherwise it strikes out
    on a wider foray so it visibly explores rather than jitters in place."""
    if ctrl.home is not None and tuple(char.position) != tuple(ctrl.home):
        return tuple(ctrl.home)
    w = engine.world.map
    x, y = char.position
    return (max(0, min(w.width - 1, x + ctrl.rng.randint(-ROAM, ROAM))),
            max(0, min(w.height - 1, y + ctrl.rng.randint(-ROAM, ROAM))))
