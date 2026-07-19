"""T4.3 New Game+ — carry a won legend into a harsher age.

Winning the campaign fired a single `[Legend]` line and nothing more.
This captures the hero's power (level, gear, gold, skills, spells) at the
moment of victory and re-applies it to a fresh, TOUGHER world — the
`ng_plus` count scales `encounters.danger_multiplier`, and the carried
high level naturally crowns tougher elites/apexes. Pure over the engine;
the GUI's `restart_ng_plus` captures, rebuilds, then applies.
"""

import logging

logger = logging.getLogger("llm_rpg.ngplus")

_STATS = ("strength", "dexterity", "constitution", "intelligence",
          "wisdom", "charisma")


def capture(engine) -> dict:
    """Snapshot the victorious hero for carry-over into New Game+."""
    p = engine.player
    from characters.equipment import to_dict as eq_to_dict
    meta = p.metadata or {}
    return {
        "ng_plus": int(meta.get("ng_plus", 0)) + 1,
        "name": p.name,
        "race": getattr(p.race, "value", "human"),
        "class": getattr(p.character_class, "value", "warrior"),
        "level": getattr(p, "level", 1),
        "xp": meta.get("xp", 0),
        "max_hp": getattr(p, "max_hp", 20),
        "gold": getattr(p, "gold", 0),
        "stats": {s: getattr(p, s, 10) for s in _STATS},
        "inventory": [it.to_dict() for it in getattr(p, "inventory", [])],
        "equipment": eq_to_dict(p),
        "spells_known": list(meta.get("spells_known", [])),
        "skills": dict(meta.get("skills", {})),
    }


def apply(engine, payload: dict) -> None:
    """Re-clothe a freshly-started hero with a captured legend."""
    if not payload:
        return
    p = engine.player
    from characters.character_types import CharacterRace, CharacterClass
    try:
        p.race = CharacterRace(payload["race"])
    except Exception:
        pass
    try:
        p.character_class = CharacterClass(payload["class"])
    except Exception:
        pass
    p.name = payload.get("name", p.name)
    for s, v in payload.get("stats", {}).items():
        setattr(p, s, v)
    p.level = payload.get("level", getattr(p, "level", 1))
    p.max_hp = payload.get("max_hp", getattr(p, "max_hp", 20))
    p.hp = p.max_hp
    p.gold = payload.get("gold", getattr(p, "gold", 0))
    ngp = int(payload.get("ng_plus", 1))
    p.metadata["ng_plus"] = ngp
    p.metadata["xp"] = payload.get("xp", 0)
    p.metadata["spells_known"] = list(payload.get("spells_known", []))
    if payload.get("skills"):
        p.metadata["skills"] = dict(payload["skills"])

    from items.item import Item
    inv = []
    for d in payload.get("inventory", []):
        try:
            inv.append(Item.from_dict(d))
        except Exception:
            pass
    p.inventory = inv
    try:
        from characters.equipment import from_dict as eq_from_dict
        eq_from_dict(p, payload.get("equipment", {}))
    except Exception:
        pass
    try:
        engine.memory_manager.add_event(
            f"[Legend] A NEW AGE DAWNS — {p.name} carries the legend of a "
            f"slain Elder Wyrm into a harsher world (New Game+{ngp}). The "
            f"wilds are fiercer here.")
    except Exception:
        pass


def danger_scale(engine) -> float:
    """The NG+ multiplier on wilderness danger (1.0 in a first game)."""
    try:
        ngp = int((engine.player.metadata or {}).get("ng_plus", 0))
    except Exception:
        ngp = 0
    return 1.0 + 0.4 * max(0, ngp)
