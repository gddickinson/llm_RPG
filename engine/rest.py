"""Sleep + the day summary (P5.6, Stardew's engine adapted lightly).

Press Enter at an inn or tavern to sleep until morning (5g for the
bed): full heal, mana restored, hunger fed — and crossing the day
boundary fires the whole nightly stack (reflection, director, faction
ticker, radiant board). You wake to a summary of what the day earned
you and a teaser of the morning's news: "tomorrow I'll..."

Day-start metrics are snapshotted at every dawn (and at engine start),
so the summary covers the day just lived.
"""

import logging
from typing import Dict, List, Optional

logger = logging.getLogger("llm_rpg.rest")

BED_COST = 5
PRIVATE_ROOM_COST = 15     # buys WELL_RESTED (+10% XP) — P12.6
WAKE_HOUR = 6


def snapshot(engine) -> Dict[str, int]:
    """Metrics captured at dawn, compared at the next sleep."""
    player = engine.player
    meta = player.metadata if player else {}
    turned_in = 0
    if engine.quest_manager:
        from quests.quest import QuestStatus
        turned_in = sum(1 for q in engine.quest_manager.quests.values()
                        if q.status == QuestStatus.TURNED_IN)
    from engine.skill_progression import total_skill_level
    return {
        "gold": player.gold if player else 0,
        "xp": int(meta.get("xp", 0)),
        "skill_total": total_skill_level(player) if player else 0,
        "quests_turned_in": turned_in,
        "kills": len(meta.get("collection", {}).get("kills", [])),
        "day": engine.world.time // (24 * 60),
    }


def can_sleep_here(engine) -> Optional[str]:
    """None if a bed is available here; else the reason it isn't."""
    inter = getattr(engine, "current_interior", None)
    if inter is not None:
        name = getattr(inter, "name", "").lower()
        if "tavern" in name or "inn" in name:
            return None
        return "There's no bed for guests here."
    loc = engine.world.get_location_at(*engine.player.position)
    if loc is not None:
        kind = (loc.properties or {}).get("type", "")
        name = loc.name.lower()
        if kind in ("tavern", "inn") or "tavern" in name or "inn" in name:
            return None
    return "You need a bed — find an inn or tavern."


def sleep(engine) -> List[str]:
    """Sleep to morning; returns the day-summary overlay lines.
    Outdoors with no inn, Enter makes CAMP instead (P12.6)."""
    reason = can_sleep_here(engine)
    if reason:
        if getattr(engine, "current_interior", None) is None and \
                getattr(engine, "current_dungeon", None) is None:
            from engine.camping import camp
            return camp(engine)
        engine.memory_manager.add_event(reason)
        return []
    player = engine.player
    if player.gold < BED_COST:
        engine.memory_manager.add_event(
            f"A bed costs {BED_COST}g — you can't cover it.")
        return []
    # Lifestyle tiers (P12.6): the private room earns its price
    tier_note = ""
    if player.gold >= PRIVATE_ROOM_COST:
        player.gold -= PRIVATE_ROOM_COST
        try:
            from characters.status_effects import apply_effect
            apply_effect(player, "well_rested", duration=240)
            tier_note = (f"You take the private room "
                         f"({PRIVATE_ROOM_COST}g) — Well Rested: "
                         f"+10% XP today.")
        except Exception:
            pass
    else:
        player.gold -= BED_COST
        tier_note = f"You take a bunk in the common room ({BED_COST}g)."

    before = getattr(engine, "_day_metrics", None) or snapshot(engine)
    # Compare before paying doesn't matter for gold delta fairness:
    # the bed is part of the day's spending
    now = engine.world.time
    minutes_per_day = 24 * 60
    player.metadata["slept_day"] = now // minutes_per_day
    wake = ((now // minutes_per_day) + 1) * minutes_per_day + \
        WAKE_HOUR * 60
    engine.world.advance_time(wake - now)

    engine.memory_manager.add_event(
        "You sleep soundly and wake at dawn.")
    # One turn tick crosses the day boundary → nightly systems fire
    engine.advance_turn()

    # Restoration (after the tick, so the night doesn't erode it)
    player.hp = player.max_hp
    try:
        from engine.spells import ensure_mana
        ensure_mana(player)
        player.metadata["mana"] = player.metadata.get("max_mana", 0)
    except Exception:
        pass
    player.metadata["hunger"] = 5
    player.metadata["fatigue"] = 0     # slept off (P11.1)
    player.metadata["sleep_debt"] = 0  # a REAL night (P12.3)
    player.metadata["wounded"] = 0     # wounds knit (P12.4)
    player.metadata["weapon_action_used"] = False   # P12.7

    after = snapshot(engine)
    lines = _summary_lines(engine, before, after)
    if tier_note:
        lines.insert(1, tier_note)
    try:   # the DM's guaranteed night beat (P12.6)
        from engine.camping import night_beat
        lines.append(night_beat(engine))
    except Exception:
        pass
    engine._day_metrics = after
    return lines


def _summary_lines(engine, before, after) -> List[str]:
    days = max(1, after["day"] - before["day"])
    lines = [f"You rest through the night. ({days} day"
             f"{'s' if days > 1 else ''} pass{'es' if days == 1 else ''})",
             ""]
    gold = after["gold"] - before["gold"]
    lines.append(f"Gold: {'+' if gold >= 0 else ''}{gold} "
                 f"(now {after['gold']})")
    xp = after["xp"] - before["xp"]
    if xp:
        lines.append(f"Combat XP earned: +{xp}")
    skills = after["skill_total"] - before["skill_total"]
    if skills:
        lines.append(f"Skill levels gained: +{skills}")
    quests = after["quests_turned_in"] - before["quests_turned_in"]
    if quests:
        lines.append(f"Quests completed: +{quests}")
    kills = after["kills"] - before["kills"]
    if kills:
        lines.append(f"New foes bested: +{kills}")
    if len(lines) == 3:
        lines.append("(A quiet day. They can't all be legends.)")

    # Tomorrow's hook: the freshest news
    lines.append("")
    teaser = None
    try:
        rumors = engine.world_director.rumors
        if rumors:
            teaser = rumors[-1]
    except Exception:
        pass
    if teaser:
        lines.append(f"Word this morning: {teaser}")
    lines.append("The tavern board may have new notices. ([Q] quests)")
    return lines
