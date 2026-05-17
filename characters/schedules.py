"""NPC daily schedules.

Each NPC class is given a default daily routine: a list of
(start_hour, activity, target_location) tuples. The currently-active
schedule entry tells the engine what the NPC "wants" to do.

This works alongside the LLM/heuristic AI: when no urgent decision is
in flight, NPCs default to their schedule. Hostile classes (brigand /
monster) have no schedule — they hunt.
"""

import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("llm_rpg.schedules")


# Schedule entry: (start_hour, activity, location_keyword)
# Activities: work, eat, drink, sleep, patrol, wander, pray, play
ScheduleEntry = Tuple[int, str, str]


SCHEDULES: Dict[str, List[ScheduleEntry]] = {
    "merchant": [
        (6, "wake", "home"),
        (7, "eat", "tavern"),
        (8, "work", "shop"),
        (12, "eat", "tavern"),
        (13, "work", "shop"),
        (19, "drink", "tavern"),
        (22, "sleep", "home"),
    ],
    "guard": [
        (6, "wake", "home"),
        (7, "eat", "tavern"),
        (8, "patrol", "village"),
        (13, "eat", "tavern"),
        (14, "patrol", "village"),
        (20, "drink", "tavern"),
        (23, "sleep", "home"),
    ],
    "villager": [
        (6, "wake", "home"),
        (7, "eat", "tavern"),
        (8, "work", "village"),
        (12, "eat", "tavern"),
        (13, "work", "village"),
        (19, "drink", "tavern"),
        (22, "sleep", "home"),
    ],
    "bard": [
        (9, "wake", "tavern"),
        (10, "play", "tavern"),
        (14, "eat", "tavern"),
        (15, "wander", "village"),
        (19, "play", "tavern"),
        (1, "sleep", "tavern"),
    ],
    "cleric": [
        (5, "wake", "temple"),
        (6, "pray", "temple"),
        (8, "work", "temple"),
        (12, "eat", "tavern"),
        (13, "work", "temple"),
        (18, "pray", "temple"),
        (21, "sleep", "temple"),
    ],
    "warrior": [
        (6, "wake", "home"),
        (7, "eat", "tavern"),
        (8, "patrol", "village"),
        (13, "eat", "tavern"),
        (14, "wander", "wilderness"),
        (19, "drink", "tavern"),
        (22, "sleep", "home"),
    ],
}


def schedule_for(class_value: str) -> List[ScheduleEntry]:
    return SCHEDULES.get(class_value, [])


def current_entry(class_value: str, hour: int) -> Optional[ScheduleEntry]:
    """Return the active schedule entry for the given hour, or None."""
    sched = schedule_for(class_value)
    if not sched:
        return None
    # Find the latest entry whose start_hour <= current hour. If none, wrap
    # to the last entry of the previous day (it covers overnight).
    matching = [e for e in sched if e[0] <= hour]
    if matching:
        return max(matching, key=lambda e: e[0])
    # Use latest entry (overnight)
    return max(sched, key=lambda e: e[0])


def activity_to_action(activity: str, location_keyword: str
                       ) -> Tuple[str, str]:
    """Translate a schedule activity into an engine action+target."""
    if activity in ("work", "patrol", "wander", "play"):
        return ("move", location_keyword)
    if activity == "eat":
        return ("move", location_keyword)  # going to tavern
    if activity == "drink":
        return ("move", location_keyword)
    if activity == "sleep":
        return ("sleep", location_keyword)
    if activity == "wake":
        return ("wait", "waking up")
    if activity == "pray":
        return ("wait", "praying")
    return ("wait", "thinking")
