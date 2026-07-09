"""What people know of you (P3.8).

A rolling ledger of notable deeds (kills, quests, diary tiers) plus
live-derived facts (level, gear worn) — the single-player substitute for
RuneScape's social status displays. Every dialog prompt carries the
digest so NPCs react to who you've become; in heuristic mode NPCs
occasionally comment on a recent deed outright.

Deeds live in `player.metadata["recent_deeds"]` (capped rolling list).
"""

import logging
import random
from typing import List

logger = logging.getLogger("llm_rpg.deeds")

MAX_DEEDS = 12
COMMENT_CHANCE = 0.35

_COMMENT_TEMPLATES = [
    "Word travels — they say you {deed}.",
    "Is it true you {deed}? That's the talk, anyway.",
    "Folk mention you {deed}. The road watches, friend.",
]


def record_deed(engine, deed: str) -> None:
    """`deed` phrased to follow 'you ...', e.g. 'slew a Wolf'."""
    deeds = engine.player.metadata.setdefault("recent_deeds", [])
    deeds.append(deed)
    del deeds[:-MAX_DEEDS]


def recent_deeds(engine, k: int = 5) -> List[str]:
    return engine.player.metadata.get("recent_deeds", [])[-k:]


def deeds_digest(engine) -> List[str]:
    """Lines for the dialog prompt: reputation + presence."""
    player = engine.player
    out = []
    out.append(f"They are level {player.level}"
               + (f" and carry themselves like a seasoned adventurer."
                  if player.level >= 5 else "."))
    try:
        from characters.equipment import get_equipment
        eq = get_equipment(player)
        weapon = eq.get("weapon")
        armor = eq.get("armor")
        visible = []
        if weapon is not None:
            visible.append(f"wielding {weapon.name}")
        if armor is not None:
            visible.append(f"wearing {armor.name}")
        if visible:
            out.append("You can see them " + ", ".join(visible) + ".")
    except Exception:
        pass
    try:
        pet = engine.pet_system.active_pet()
        if pet:
            out.append(f"A small {pet['kind']} trails at their heel.")
    except Exception:
        pass
    for deed in recent_deeds(engine, k=4):
        out.append(f"Word around the region: they {deed}.")
    return out


def prompt_block(engine) -> str:
    lines = deeds_digest(engine)
    if not lines:
        return ""
    return ("WHAT PEOPLE KNOW OF THE PLAYER (react naturally — respect, "
            "fear, curiosity — as fits your character):\n"
            + "\n".join(f"- {line}" for line in lines))


def heuristic_comment(engine, rng: random.Random = None) -> str:
    """An occasional spoken comment on a recent deed (no LLM needed)."""
    rng = rng or random
    deeds = recent_deeds(engine, k=5)
    if not deeds or rng.random() > COMMENT_CHANCE:
        return ""
    template = rng.choice(_COMMENT_TEMPLATES)
    return template.format(deed=rng.choice(deeds))
