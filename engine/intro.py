"""The cold-open prologue (GAP.7) — a new game's missing narrative hook.

`intro_text(engine)` composes a short, class- and world-aware framing
(data/intro.json) that sets who you are, where you've arrived, and what
to do first — shown once, before play. Pure + resilient; `ui/intro_screen`
draws it, and it is shown only for a NEW game (gated by `should_show`).
"""

import json
import logging
import os

logger = logging.getLogger("llm_rpg.intro")

_DATA = os.path.join(os.path.dirname(__file__), "..", "data", "intro.json")


def _load():
    try:
        with open(_DATA, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception as e:                        # pragma: no cover
        logger.info(f"Intro data unavailable: {e}")
        return {}


def should_show(engine) -> bool:
    try:
        return not (engine.player.metadata or {}).get("intro_seen")
    except Exception:
        return False


def mark_seen(engine) -> None:
    try:
        engine.player.metadata["intro_seen"] = True
    except Exception:
        pass


def _first_goal(engine):
    """Point at a concrete first objective — the main quest if there is
    one, else the opening rumor, else the board."""
    try:
        from quests.quest import QuestStatus
        qm = engine.quest_manager
        mains = [q for q in qm.quests.values()
                 if (q.metadata or {}).get("main")
                 and q.status == QuestStatus.ACTIVE]
        if mains:
            return f"Your charge: {mains[0].name}."
    except Exception:
        pass
    try:
        for ev in reversed(engine.memory_manager.game_history[-40:]):
            txt = str(getattr(ev, "get", lambda *_: "")("event") if
                      isinstance(ev, dict) else ev)
            if "rumor" in txt.lower() or "[Realm]" in txt:
                return None
    except Exception:
        pass
    return None


def intro_text(engine):
    """Return (title, [lines]) for the prologue overlay."""
    data = _load()
    p = engine.player
    name = getattr(p, "name", "Adventurer")
    cls = getattr(getattr(p, "character_class", None), "value", "default")
    race = getattr(getattr(p, "race", None), "value", "")
    world = getattr(engine, "world_kind", None) or "default"

    openings = data.get("openings", {})
    opening = openings.get(cls, openings.get("default", ""))
    worlds = data.get("worlds", {})
    world_line = worlds.get(world, worlds.get("default", ""))

    lines = []
    who = f"You are {name}"
    if race and cls != "default":
        who += f", a {race} {cls}."
    else:
        who += "."
    lines.append(who)
    lines.append("")
    if opening:
        lines.append(opening)
    if world_line:
        lines.append("")
        lines.append(world_line)
    goal = _first_goal(engine)
    if goal:
        lines += ["", goal]
    call = data.get("call")
    if call:
        lines += ["", call]
    hints = data.get("hints", [])
    if hints:
        lines += ["", "— " + hints[0]]
    return (f"The Tale of {name} Begins", lines)
