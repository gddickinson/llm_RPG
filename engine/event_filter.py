"""Event-log display filter (George, 2026-07-11).

The memory keeps EVERY event (the topic journal, deeds, sound and
playtest assertions all read it — load-bearing). But the HUD should
show only what the player could plausibly know, and not drown them.
This filters at DISPLAY time, never touching memory.

Two rules:

LOCATION — inside a building or dungeon you can't see the street:
ambient overworld lines (your own footsteps, distant NPC barks,
weather, world-clash noise) are hidden while you're in a zone.
World NEWS ([Realm]/[Board]/[DM]/[Legend]) still shows — that's
word reaching you, not sight.

VERBOSITY — a per-player setting (quiet / normal / verbose), cycled
with SHIFT+L. Quiet keeps only what matters (your actions, combat,
[!] danger, news); normal adds law/quest/social; verbose shows all,
including footsteps.
"""

import logging

logger = logging.getLogger("llm_rpg.event_filter")

VERBOSITY = ("quiet", "normal", "verbose")
DEFAULT_VERBOSITY = "normal"

# category -> which verbosity levels show it
_LEVELS = {
    "critical": {"quiet", "normal", "verbose"},   # [!] danger
    "combat": {"quiet", "normal", "verbose"},
    "player": {"quiet", "normal", "verbose"},     # your deliberate acts
    "news": {"quiet", "normal", "verbose"},       # world news / rumor
    "law": {"normal", "verbose"},
    "social": {"normal", "verbose"},
    "ambient": {"verbose"},                        # footsteps, barks
}

# prefixes that are world NEWS — reach you as word, never gated by
# location (you hear the rumor inside the tavern too)
_NEWS_PREFIXES = ("[Realm]", "[Board]", "[DM]", "[Legend]",
                  "[Collection]", "[Topic]", "[Lesson]", "[Overnight]")
_LAW_PREFIXES = ("[Law]", "[Clash]")


def categorize(text: str) -> str:
    t = text.strip()
    if t.startswith("[!]"):
        return "critical"
    for p in _NEWS_PREFIXES:
        if t.startswith(p):
            return "news"
    if t.startswith("[Law]"):
        return "law"
    if t.startswith("[Clash]"):
        return "ambient"      # a fight you may not see (location-gated)
    if t.startswith(("[Bond]", "[Secret]", "[Lesson]")):
        return "social"
    low = t.lower()
    if low.startswith("you move to") or "wanders" in low or \
            "strolls" in low or "mutters" in low or \
            "hums" in low or low.startswith("the ") and \
            ("weather" in low or "wind" in low):
        return "ambient"
    if low.startswith(("you ", "your ")):
        return "player"
    # attacks / damage / defeats / spells
    if any(w in low for w in ("attack", "hits", "damage", "slain",
                              "defeated", "misses", "strikes",
                              "casts", "burning", "crushed")):
        return "combat"
    return "player"       # default: keep it (better shown than lost)


def verbosity(engine) -> str:
    v = engine.player.metadata.get("log_verbosity", DEFAULT_VERBOSITY)
    return v if v in VERBOSITY else DEFAULT_VERBOSITY


def cycle_verbosity(engine) -> str:
    cur = verbosity(engine)
    nxt = VERBOSITY[(VERBOSITY.index(cur) + 1) % len(VERBOSITY)]
    engine.player.metadata["log_verbosity"] = nxt
    engine.memory_manager.add_event(
        f"[Board] Event log: {nxt} detail.")
    return nxt


def _indoors(engine) -> bool:
    try:
        return engine.active_zone() is not None
    except Exception:
        return False


def should_display(engine, text: str, level: str = None) -> bool:
    level = level or verbosity(engine)
    cat = categorize(text)
    if level not in _LEVELS.get(cat, {"normal", "verbose"}):
        return False
    # inside a building, the street is out of sight: drop ambient +
    # overworld clashes (news still reaches you)
    if _indoors(engine) and cat == "ambient":
        return False
    return True


def filtered_recent(engine, count: int = 12):
    """The display list: walk history newest-first, keep what should
    show, return oldest-first up to `count`."""
    hist = engine.memory_manager.game_history
    out = []
    for entry in reversed(hist):
        text = entry.get("event", "")
        if should_display(engine, text):
            out.append(text)
            if len(out) >= count:
                break
    return list(reversed(out))
