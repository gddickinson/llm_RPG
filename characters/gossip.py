"""NPC gossip — flavor lines drawn from recent in-game events.

Gossip pool:
- Static class-based templates ("I hear the troll's still on the road.")
- Dynamic lines pulled from memory_manager event history that mention
  another NPC by name.
"""

import logging
import random
from typing import List

logger = logging.getLogger("llm_rpg.gossip")


STATIC_GOSSIP = [
    "Strange lights in the mountains lately. Some say a wizard's come back.",
    "Bandits hit a caravan a week back — wasn't pretty.",
    "Old Anselm at the chapel could use more healing herbs.",
    "Karim the guard's been organizing a troll hunt.",
    "Melody's working on a new song. They say it's about the troll.",
    "Durgan and Tova haven't spoken in years, family quarrel.",
    "The river's been low this season. Could be a dry summer ahead.",
    "Someone heard wolves howling closer to the village last night.",
]


def random_gossip(rng: random.Random = None) -> str:
    rng = rng or random
    return rng.choice(STATIC_GOSSIP)


def fresh_gossip_about_npcs(memory_manager, exclude_speaker_id: str,
                            other_npc_names: List[str],
                            max_lines: int = 1,
                            rng: random.Random = None) -> List[str]:
    """Return a few recent event lines that mention any of the other NPCs."""
    rng = rng or random
    history = memory_manager.get_recent_history(count=30)
    hits = []
    for event in reversed(history):
        for name in other_npc_names:
            if name.lower() in event.lower():
                hits.append(event)
                break
        if len(hits) >= max_lines:
            break
    return hits


def gossip_for(npc, engine, max_lines: int = 1) -> List[str]:
    """Compose a list of gossip lines for `npc` to share."""
    rng = random.Random()
    lines = []

    # Pull family-related context first if available
    try:
        from characters.families import family_of, relation_to
        fam = family_of(npc.id)
        if fam:
            if fam.spouse:
                spouse = engine.npc_manager.get_npc(fam.spouse)
                if spouse and rng.random() < 0.35:
                    lines.append(f"My spouse, {spouse.name}, "
                                 f"runs the {spouse.home_location if hasattr(spouse, 'home_location') else 'place'}.")
            if fam.siblings and rng.random() < 0.25:
                sib_id = rng.choice(fam.siblings)
                sib = engine.npc_manager.get_npc(sib_id)
                if sib:
                    lines.append(f"My sibling {sib.name}? "
                                 f"We get on... mostly.")
    except Exception:
        pass

    # Recent gossip from the world's events
    other_names = [
        n.name for n in engine.npc_manager.npcs.values()
        if n.id != npc.id and n.is_active()
    ]
    if other_names:
        recent = fresh_gossip_about_npcs(
            engine.memory_manager, npc.id, other_names,
            max_lines=1, rng=rng)
        lines.extend(recent)

    # Static line as filler
    if len(lines) < max_lines:
        lines.append(random_gossip(rng))

    return lines[:max_lines]
