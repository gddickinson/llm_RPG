"""The main arc — a spine, a climax, an ending (P21.2).

The game had a hundred things to do and nothing to do them FOR: no
overarching story, no world-goal, no ending. This is the spine. A wizard
reads dark omens; you cull the stirring wilds, seek the source in the
deep, learn the old lore of the wyrms, survive the gathering night, and
face the Elder Wyrm in its lair. Slay it and the shadow over the realm
lifts — the campaign is WON, and the age you lived closes with a reading
of its own chronicle.

The arc is authored data (`main: true` quests chained by prereq); this
module is the thin spine over it: which quests form the main line, whether
the campaign is won, and the once-only ending beat + summary drawn from the
P20.5 chronicle. `check_finale` runs each turn and fires the ending the
moment the finale's flag is set.
"""

import logging

logger = logging.getLogger("llm_rpg.campaign")


def _flags(engine) -> dict:
    return engine.player.metadata.setdefault("quest_flags", {})


def main_line(engine) -> list:
    """The main-quest ids, in chain order."""
    from quests.quest_templates import QUEST_TEMPLATES, create_quest
    mains = [qid for qid in QUEST_TEMPLATES
             if create_quest(qid).metadata.get("main")]
    return sorted(mains)


def finale_id(engine):
    from quests.quest_templates import QUEST_TEMPLATES, create_quest
    for qid in QUEST_TEMPLATES:
        if create_quest(qid).metadata.get("main_finale"):
            return qid
    return None


def is_won(engine) -> bool:
    return bool(_flags(engine).get("campaign_won"))


def summary(engine) -> list:
    """The ending — a triumphant close over the saga you wrote."""
    out = ["", "THE SHADOW LIFTS",
           "The Elder Wyrm is slain, and the realm draws its first easy",
           "breath in an age. This is the chronicle of your years:", ""]
    try:
        chron = engine.chronicle.lines()
        # skip the chronicle's own header, keep the entries
        out += [ln for ln in chron if ln and "Chronicle of the Age" not in ln
                and "saga of your own" not in ln]
    except Exception:
        pass
    out += ["", "So ends the age of your making. The realm remembers."]
    return out


def check_finale(engine) -> bool:
    """Fire the ending ONCE, the turn the campaign is won. Returns True the
    turn it fires."""
    if not is_won(engine):
        return False
    if engine.player.metadata.get("ending_shown"):
        return False
    engine.player.metadata["ending_shown"] = True
    engine.memory_manager.add_event(
        "[Legend] The Elder Wyrm falls — the shadow over the realm is lifted, "
        "and the age is won!")
    return True
