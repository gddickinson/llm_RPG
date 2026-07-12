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


def named_goal(ctrl, engine, char):
    """The nearest UNVISITED named place the hero's calling draws it to,
    else any unvisited place. Records the choice on `ctrl.goal_name`."""
    cls = getattr(getattr(char, "character_class", None), "value", "")
    draw = CLASS_DRAW.get(cls, ())
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
    return loc.center()


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


def pick_goal(ctrl, engine, char):
    """An away hero potters back toward home (M.3); otherwise it strikes out
    on a wider foray so it visibly explores rather than jitters in place."""
    if ctrl.home is not None and tuple(char.position) != tuple(ctrl.home):
        return tuple(ctrl.home)
    w = engine.world.map
    x, y = char.position
    return (max(0, min(w.width - 1, x + ctrl.rng.randint(-ROAM, ROAM))),
            max(0, min(w.height - 1, y + ctrl.rng.randint(-ROAM, ROAM))))
